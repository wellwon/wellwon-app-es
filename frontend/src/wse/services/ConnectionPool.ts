// =============================================================================
// File: src/wse/services/ConnectionPool.ts
// Description: Enhanced connection pool with health scoring and load balancing (FIXED V2)
// =============================================================================

import { logger, MessageCategory, WS_PROTOCOL_VERSION } from '@/wse';

interface EndpointHealth {
  url: string;
  score: number; // 0-100
  lastSuccess: number | null;
  lastFailure: number | null;
  consecutiveFailures: number;
  consecutiveSuccesses: number;
  averageLatency: number;
  latencyHistory: number[];
  totalRequests: number;
  failedRequests: number;
  lastChecked: number;
}

interface ConnectionMetrics {
  endpoint: string;
  connectedAt: number;
  messagesReceived: number;
  messagesSent: number;
  bytesReceived: number;
  bytesSent: number;
  lastActivity: number;
}

export class ConnectionPool {
  private endpoints: Map<string, EndpointHealth> = new Map();
  private connections: Map<string, WebSocket[]> = new Map();
  private connectionMetrics: Map<string, ConnectionMetrics> = new Map();
  private healthScores: Map<string, number> = new Map();
  private activeEndpoint: string | null = null;
  private preferredEndpoint: string | null = null;
  private isDestroyed = false;

  private config = {
    maxPerEndpoint: 3,
    healthCheckInterval: 30000,
    latencyHistorySize: 100,
    scoreDecayRate: 0.1,
    minHealthScore: 10,
    loadBalancingStrategy: 'weighted-random' as 'weighted-random' | 'least-connections' | 'round-robin',
    healthCheckTimeout: 5000,
    enableHealthCheck: true,
  };

  private healthCheckTimer: NodeJS.Timeout | null = null;
  private roundRobinIndex = 0;
  private healthCheckInProgress = false;

  constructor(config?: any) {
    Object.assign(this.config, config);

    // Initialize endpoints from config if provided
    const endpoints = config?.endpoints || [];

    // Ensure endpoints is an array of strings
    const endpointStrings: string[] = Array.isArray(endpoints)
      ? endpoints.filter((e): e is string => typeof e === 'string')
      : [];

    // Deduplicate endpoints
    const uniqueEndpoints = Array.from(new Set(endpointStrings));

    uniqueEndpoints.forEach((endpoint) => {
      this.addEndpoint(endpoint);
    });

    // Only start health monitoring if endpoints exist
    if (this.config.enableHealthCheck && this.config.healthCheckInterval > 0 && uniqueEndpoints.length > 0) {
      this.startHealthMonitoring();
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Core Methods
  // ─────────────────────────────────────────────────────────────────────────

  getBestEndpoint(): string {
    if (this.isDestroyed) {
      throw new Error('ConnectionPool has been destroyed');
    }

    const healthyEndpoints = this.getHealthyEndpoints();

    if (healthyEndpoints.length === 0) {
      // All endpoints unhealthy, return the least unhealthy
      const allEndpoints = Array.from(this.endpoints.entries());
      if (allEndpoints.length === 0) {
        throw new Error('No endpoints available');
      }
      allEndpoints.sort((a, b) => b[1].score - a[1].score);
      return allEndpoints[0]?.[0];
    }

    // Check if we have a preferred endpoint that's healthy
    if (this.preferredEndpoint) {
      const preferredHealth = this.endpoints.get(this.preferredEndpoint);
      if (preferredHealth && preferredHealth.score > this.config.minHealthScore) {
        return this.preferredEndpoint;
      }
    }

    // Apply load balancing strategy
    switch (this.config.loadBalancingStrategy) {
      case 'weighted-random':
        return this.selectWeightedRandom(healthyEndpoints);
      case 'least-connections':
        return this.selectLeastConnections(healthyEndpoints);
      case 'round-robin':
        return this.selectRoundRobin(healthyEndpoints);
      default:
        return healthyEndpoints[0][0];
    }
  }

  recordSuccess(endpoint: string, latency?: number): void {
    if (this.isDestroyed) return;

    const health = this.endpoints.get(endpoint);
    if (!health) return;

    health.lastSuccess = Date.now();
    health.consecutiveSuccesses++;
    health.consecutiveFailures = 0;
    health.totalRequests++;

    // Update latency if provided
    if (latency !== undefined && latency >= 0) {
      health.latencyHistory.push(latency);
      if (health.latencyHistory.length > this.config.latencyHistorySize) {
        health.latencyHistory.shift();
      }
      health.averageLatency = this.calculateAverageLatency(health.latencyHistory);
    }

    // Update health score
    this.updateHealthScore(endpoint);

    // Update backward-compatible healthScores map
    this.healthScores.set(endpoint, health.score);

    logger.debug(`Recorded success for ${endpoint}, score: ${health.score}`);
  }

  recordFailure(endpoint: string): void {
    if (this.isDestroyed) return;

    const health = this.endpoints.get(endpoint);
    if (!health) return;

    health.lastFailure = Date.now();
    health.consecutiveFailures++;
    health.consecutiveSuccesses = 0;
    health.totalRequests++;
    health.failedRequests++;

    // Update health score more aggressively for failures
    this.updateHealthScore(endpoint, true);

    // Update backward-compatible healthScores map
    this.healthScores.set(endpoint, health.score);

    logger.warn(`Recorded failure for ${endpoint}, score: ${health.score}`);
  }

  addConnection(endpoint: string, ws: WebSocket): void {
    if (this.isDestroyed) return;

    if (!this.connections.has(endpoint)) {
      this.connections.set(endpoint, []);
    }

    const connections = this.connections.get(endpoint)!;

    // Check if connection already exists
    if (connections.includes(ws)) {
      return;
    }

    if (connections.length < this.config.maxPerEndpoint) {
      connections.push(ws);

      // Initialize metrics for this connection
      const connectionId = `${endpoint}:${Date.now()}:${Math.random().toString(36).substr(2, 9)}`;
      this.connectionMetrics.set(connectionId, {
        endpoint,
        connectedAt: Date.now(),
        messagesReceived: 0,
        messagesSent: 0,
        bytesReceived: 0,
        bytesSent: 0,
        lastActivity: Date.now(),
      });

      logger.info(`Added connection to ${endpoint}, total: ${connections.length}`);
    } else {
      logger.warn(`Max connections (${this.config.maxPerEndpoint}) reached for ${endpoint}`);
    }
  }

  removeConnection(endpoint: string, ws: WebSocket): void {
    if (this.isDestroyed) return;

    const connections = this.connections.get(endpoint);
    if (connections) {
      const index = connections.indexOf(ws);
      if (index >= 0) {
        connections.splice(index, 1);
        logger.info(`Removed connection from ${endpoint}, remaining: ${connections.length}`);
      }
    }
  }

  getActiveConnection(): WebSocket | null {
    if (this.isDestroyed) return null;

    if (this.activeEndpoint) {
      const connections = this.connections.get(this.activeEndpoint);
      if (connections && connections.length > 0) {
        return connections.find(ws => ws.readyState === WebSocket.OPEN) || null;
      }
    }
    return null;
  }

  setActiveEndpoint(endpoint: string): void {
    if (!this.isDestroyed) {
      this.activeEndpoint = endpoint;
    }
  }

  setPreferredEndpoint(endpoint: string): void {
    if (!this.isDestroyed) {
      this.preferredEndpoint = endpoint;
    }
  }

  hasEndpoint(endpoint: string): boolean {
    return this.endpoints.has(endpoint);
  }

  addEndpoint(endpoint: string): void {
    if (this.isDestroyed) return;

    if (!this.endpoints.has(endpoint)) {
      this.endpoints.set(endpoint, {
        url: endpoint,
        score: 100,
        lastSuccess: null,
        lastFailure: null,
        consecutiveFailures: 0,
        consecutiveSuccesses: 0,
        averageLatency: 0,
        latencyHistory: [],
        totalRequests: 0,
        failedRequests: 0,
        lastChecked: Date.now(),
      });

      this.healthScores.set(endpoint, 100);
      this.connections.set(endpoint, []);

      logger.info(`Added endpoint: ${endpoint}`);

      // Start health monitoring if it wasn't started
      if (this.config.enableHealthCheck && !this.healthCheckTimer && this.endpoints.size > 0) {
        this.startHealthMonitoring();
      }
    }
  }

  getHealthScores(): Record<string, number> {
    const scores: Record<string, number> = {};
    this.endpoints.forEach((health, endpoint) => {
      scores[endpoint] = health.score;
    });
    return scores;
  }

  getEndpointStats(): Array<{
    url: string;
    healthScore: number;
    connectionCount: number;
    isActive: boolean;
    isPreferred: boolean;
  }> {
    const stats = [];

    for (const [endpoint, health] of this.endpoints) {
      const connections = this.connections.get(endpoint) || [];

      stats.push({
        url: endpoint,
        healthScore: health.score,
        connectionCount: connections.filter(ws => ws.readyState === WebSocket.OPEN).length,
        isActive: endpoint === this.activeEndpoint,
        isPreferred: endpoint === this.preferredEndpoint,
      });
    }

    return stats;
  }

  getActiveEndpoint(): string | null {
    return this.activeEndpoint;
  }

  getPreferredEndpoint(): string | null {
    return this.preferredEndpoint;
  }

  closeAll(): void {
    this.connections.forEach((connections, endpoint) => {
      connections.forEach(ws => {
        try {
          if (ws.readyState === WebSocket.OPEN) {
            ws.close(1000, 'Pool closing');
          }
        } catch (error) {
          logger.error(`Error closing WebSocket for ${endpoint}:`, error);
        }
      });
    });
    this.connections.clear();
    this.connectionMetrics.clear();
    this.activeEndpoint = null;
  }

  destroy(): void {
    this.isDestroyed = true;

    // Stop health monitoring
    if (this.healthCheckTimer) {
      clearInterval(this.healthCheckTimer);
      this.healthCheckTimer = null;
    }

    this.closeAll();
    this.endpoints.clear();
    this.healthScores.clear();
    this.preferredEndpoint = null;

    logger.info('ConnectionPool destroyed');
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Private Methods
  // ─────────────────────────────────────────────────────────────────────────

  private selectWeightedRandom(endpoints: Array<[string, EndpointHealth]>): string {
    const totalScore = endpoints.reduce((sum, [_, health]) => sum + health.score, 0);

    if (totalScore === 0) {
      return endpoints[0][0];
    }

    const random = Math.random() * totalScore;

    let accumulated = 0;
    for (const [endpoint, health] of endpoints) {
      accumulated += health.score;
      if (random <= accumulated) {
        return endpoint;
      }
    }

    return endpoints[0][0];
  }

  private selectLeastConnections(endpoints: Array<[string, EndpointHealth]>): string {
    let minConnections = Infinity;
    let bestEndpoint = endpoints[0][0];

    for (const [endpoint] of endpoints) {
      const connections = this.connections.get(endpoint)?.filter(
        ws => ws.readyState === WebSocket.OPEN
      ).length || 0;

      if (connections < minConnections) {
        minConnections = connections;
        bestEndpoint = endpoint;
      }
    }

    return bestEndpoint;
  }

  private selectRoundRobin(endpoints: Array<[string, EndpointHealth]>): string {
    const endpoint = endpoints[this.roundRobinIndex % endpoints.length][0];
    this.roundRobinIndex++;
    return endpoint;
  }

  private updateHealthScore(endpoint: string, isFailure = false): void {
    const health = this.endpoints.get(endpoint);
    if (!health) return;

    let score = health.score;

    if (isFailure) {
      // Progressive penalty for consecutive failures
      const penalty = Math.min(30, health.consecutiveFailures * 10);
      score = Math.max(this.config.minHealthScore, score - penalty);
    } else {
      // Recovery bonus
      const baseIncrease = 5;
      const latencyBonus = this.calculateLatencyBonus(health.averageLatency);
      const consistencyBonus = Math.min(10, health.consecutiveSuccesses * 2);

      score = Math.min(100, score + baseIncrease + latencyBonus + consistencyBonus);
    }

    // Apply time-based decay
    const timeSinceLastCheck = Date.now() - health.lastChecked;
    if (timeSinceLastCheck > this.config.healthCheckInterval) {
      const decayFactor = 1 - (this.config.scoreDecayRate * timeSinceLastCheck / this.config.healthCheckInterval);
      score = Math.max(this.config.minHealthScore, score * decayFactor);
    }

    health.score = Math.round(score);
    health.lastChecked = Date.now();
  }

  private calculateLatencyBonus(averageLatency: number): number {
    if (averageLatency === 0) return 0;
    if (averageLatency < 50) return 5;
    if (averageLatency < 100) return 3;
    if (averageLatency < 200) return 1;
    return 0;
  }

  private calculateAverageLatency(history: number[]): number {
    if (history.length === 0) return 0;

    // Use weighted average giving more weight to recent values
    let weightedSum = 0;
    let weightSum = 0;

    history.forEach((latency, index) => {
      const weight = index + 1; // More recent values have higher weight
      weightedSum += latency * weight;
      weightSum += weight;
    });

    return Math.round(weightedSum / weightSum);
  }

  private getHealthyEndpoints(): Array<[string, EndpointHealth]> {
    return Array.from(this.endpoints.entries())
      .filter(([_, health]) => health.score > this.config.minHealthScore)
      .sort((a, b) => b[1].score - a[1].score);
  }

  // FIXED: Improved health monitoring
  private startHealthMonitoring(): void {
    if (this.healthCheckTimer || this.isDestroyed || this.config.healthCheckInterval <= 0) return;

    // Initial health check after a short delay
    setTimeout(() => {
      if (!this.isDestroyed) {
        this.performHealthCheck().catch(error => {
          logger.error('Initial health check failed:', error);
        });
      }
    }, 5000);

    // Periodic health checks
    this.healthCheckTimer = setInterval(() => {
      if (!this.isDestroyed && !this.healthCheckInProgress) {
        this.performHealthCheck().catch(error => {
          logger.error('Periodic health check failed:', error);
        });
      }
    }, this.config.healthCheckInterval);
  }

  private async performHealthCheck(): Promise<void> {
    if (this.isDestroyed || this.healthCheckInProgress) return;

    this.healthCheckInProgress = true;

    try {
      const promises = [];

      for (const [endpoint, health] of this.endpoints) {
        // Skip if recently checked
        if (Date.now() - health.lastChecked < this.config.healthCheckInterval / 2) {
          continue;
        }

        promises.push(this.checkEndpointHealth(endpoint));
      }

      // Execute health checks in parallel with timeout
      await Promise.allSettled(promises);
    } finally {
      this.healthCheckInProgress = false;
    }
  }

  private async checkEndpointHealth(endpoint: string): Promise<void> {
    try {
      // Only perform WebSocket-based health checks
      await this.performWebSocketHealthCheck(endpoint);
    } catch (error) {
      logger.debug(`Health check for ${endpoint} encountered an error:`, error);
    }
  }

  private async performWebSocketHealthCheck(endpoint: string): Promise<void> {
    const existingConnection = this.connections.get(endpoint)?.find(
      ws => ws.readyState === WebSocket.OPEN
    );

    if (existingConnection) {
      // Use existing connection for ping with WSE prefix (Protocol v2)
      try {
        const start = Date.now();
        const pingMessage = {
          t: 'PING',
          p: { timestamp: start },
          v: WS_PROTOCOL_VERSION,
        };
        existingConnection.send(`${MessageCategory.SYSTEM}${JSON.stringify(pingMessage)}`);

        // Record success - actual latency will be recorded when PONG is received
        this.recordSuccess(endpoint);
        logger.debug(`WebSocket ping sent to ${endpoint}`);
      } catch (error) {
        // Connection failed to send ping
        this.recordFailure(endpoint);
        logger.debug(`WebSocket ping failed for ${endpoint}:`, error);
      }
    } else {
      // No active connection exists
      const health = this.endpoints.get(endpoint);
      if (health && health.lastFailure && !health.lastSuccess) {
        // Only maintain failure state if we've previously failed to connect
        logger.debug(`No active WebSocket connection for ${endpoint}`);
      }
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Additional Methods
  // ─────────────────────────────────────────────────────────────────────────

  getDetailedStats(): {
    endpoints: Array<{
      url: string;
      health: EndpointHealth;
      connections: number;
      metrics: ConnectionMetrics[];
    }>;
    summary: {
      totalEndpoints: number;
      healthyEndpoints: number;
      totalConnections: number;
      averageHealthScore: number;
    };
  } {
    const endpointStats = [];
    let totalConnections = 0;
    let totalScore = 0;
    let healthyCount = 0;

    for (const [endpoint, health] of this.endpoints) {
      const connections = this.connections.get(endpoint) || [];
      const activeConnections = connections.filter(ws => ws.readyState === WebSocket.OPEN).length;
      const metrics: ConnectionMetrics[] = [];

      // Collect metrics for this endpoint
      this.connectionMetrics.forEach((metric, id) => {
        if (id.startsWith(endpoint)) {
          metrics.push(metric);
        }
      });

      endpointStats.push({
        url: endpoint,
        health,
        connections: activeConnections,
        metrics,
      });

      totalConnections += activeConnections;
      totalScore += health.score;
      if (health.score > this.config.minHealthScore) {
        healthyCount++;
      }
    }

    return {
      endpoints: endpointStats,
      summary: {
        totalEndpoints: this.endpoints.size,
        healthyEndpoints: healthyCount,
        totalConnections,
        averageHealthScore: this.endpoints.size > 0 ? Math.round(totalScore / this.endpoints.size) : 0,
      },
    };
  }

  setLoadBalancingStrategy(strategy: 'weighted-random' | 'least-connections' | 'round-robin'): void {
    if (!this.isDestroyed) {
      this.config.loadBalancingStrategy = strategy;
      this.roundRobinIndex = 0; // Reset round-robin index
      logger.info(`Load balancing strategy changed to: ${strategy}`);
    }
  }

  setHealthCheckEnabled(enabled: boolean): void {
    if (this.isDestroyed) return;

    this.config.enableHealthCheck = enabled;

    if (enabled && !this.healthCheckTimer && this.config.healthCheckInterval > 0 && this.endpoints.size > 0) {
      this.startHealthMonitoring();
    } else if (!enabled && this.healthCheckTimer) {
      clearInterval(this.healthCheckTimer);
      this.healthCheckTimer = null;
    }
  }
}