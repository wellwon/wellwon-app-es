// =============================================================================
// File: src/wse/services/NetworkMonitor.ts
// Description: Network quality monitoring and diagnostics service
// =============================================================================

import {
  NetworkDiagnostics,
  ConnectionQuality
} from '@/wse';
import { useWSEStore } from '@/wse';
import { logger } from '@/wse';

export class NetworkMonitor {
  private latencyHistory: number[] = [];
  private packetsSent = 0;
  private packetsReceived = 0;
  private bytesHistory: Array<{ timestamp: number; bytes: number }> = [];
  private lastDiagnostics: NetworkDiagnostics | null = null;
  private diagnosticsInterval: NodeJS.Timeout | null = null;

  constructor(
    private maxHistorySize = 100,
    private diagnosticsIntervalMs = 30000 // 30 seconds
  ) {
    this.startDiagnostics();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Metrics Recording
  // ─────────────────────────────────────────────────────────────────────────

  recordLatency(latency: number): void {
    this.latencyHistory.push(latency);

    // Maintain history size
    if (this.latencyHistory.length > this.maxHistorySize) {
      this.latencyHistory.shift();
    }

    // Update store
    const store = useWSEStore.getState();
    store.recordLatency(latency);
  }

  recordPacketSent(): void {
    this.packetsSent++;
  }

  recordPacketReceived(): void {
    this.packetsReceived++;
  }

  recordBytes(bytes: number): void {
    this.bytesHistory.push({
      timestamp: Date.now(),
      bytes
    });

    // Keep only the last minute
    const cutoff = Date.now() - 60000;
    this.bytesHistory = this.bytesHistory.filter(b => b.timestamp > cutoff);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Analysis
  // ─────────────────────────────────────────────────────────────────────────

  analyze(): NetworkDiagnostics {
    const avgLatency = this.calculateAverage(this.latencyHistory);
    const jitter = this.calculateJitter();
    const packetLoss = this.calculatePacketLoss();
    const quality = this.determineQuality(avgLatency, jitter, packetLoss);
    const suggestions = this.generateSuggestions(quality, avgLatency, jitter, packetLoss);

    // TODO: Future enhancements - these metrics are calculated for future use
    // when we expand NetworkDiagnostics interface to include them
    // const bandwidth = this.calculateBandwidth();
    // const cpuUsage = this.estimateCPUUsage();
    // const memoryUsage = this.getMemoryUsage();

    const diagnostics: NetworkDiagnostics = {
      quality,
      stability: 100 - (jitter / 100) * 50,
      jitter,
      packetLoss,
      roundTripTime: avgLatency,
      suggestions,
      lastAnalysis: Date.now(),
    };

    this.lastDiagnostics = diagnostics;
    return diagnostics;
  }

  private calculateAverage(values: number[]): number {
    if (values.length === 0) return 0;
    return values.reduce((a, b) => a + b, 0) / values.length;
  }

  private calculateJitter(): number {
    if (this.latencyHistory.length < 2) return 0;

    let sumDiff = 0;
    for (let i = 1; i < this.latencyHistory.length; i++) {
      sumDiff += Math.abs(this.latencyHistory[i] - this.latencyHistory[i - 1]);
    }

    return sumDiff / (this.latencyHistory.length - 1);
  }

  private calculatePacketLoss(): number {
    if (this.packetsSent === 0) return 0;
    return ((this.packetsSent - this.packetsReceived) / this.packetsSent) * 100;
  }

  private calculateBandwidth(): number {
    if (this.bytesHistory.length === 0) return 0;

    const totalBytes = this.bytesHistory.reduce((sum, b) => sum + b.bytes, 0);
    const duration = (Date.now() - this.bytesHistory[0].timestamp) / 1000; // seconds

    return totalBytes / duration; // bytes per second
  }

  private determineQuality(
    avgLatency: number,
    jitter: number,
    packetLoss: number
  ): ConnectionQuality {
    // Quality thresholds
    if (avgLatency > 300 || jitter > 100 || packetLoss > 5) {
      return ConnectionQuality.POOR;
    } else if (avgLatency > 150 || jitter > 50 || packetLoss > 2) {
      return ConnectionQuality.FAIR;
    } else if (avgLatency > 75 || jitter > 25 || packetLoss > 0.5) {
      return ConnectionQuality.GOOD;
    }
    return ConnectionQuality.EXCELLENT;
  }

  private generateSuggestions(
    quality: ConnectionQuality,
    avgLatency: number,
    jitter: number,
    packetLoss: number
  ): string[] {
    const suggestions: string[] = [];

    if (quality === ConnectionQuality.POOR || quality === ConnectionQuality.FAIR) {
      if (avgLatency > 200) {
        suggestions.push('High latency detected. Consider checking your network connection or switching to a closer server.');
      }
      if (jitter > 75) {
        suggestions.push('High network jitter detected. This may cause unstable connections.');
      }
      if (packetLoss > 3) {
        suggestions.push('Significant packet loss detected. Check for network congestion or interference.');
      }

      // General suggestions
      suggestions.push('Try closing unnecessary applications that use network bandwidth.');
      suggestions.push('Consider using a wired connection instead of Wi-Fi for better stability.');
    }

    return suggestions;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // System Metrics
  // ─────────────────────────────────────────────────────────────────────────

  private estimateCPUUsage(): number {
    // In a browser, we can't get real CPU usage
    // Estimate based on main thread blocking
    if ('performance' in window && 'measure' in performance) {
      try {
        performance.mark('cpu-check-start');

        // Do some work
        let sum = 0;
        const iterations = 100000;
        for (let i = 0; i < iterations; i++) {
          sum += Math.sqrt(i);
        }

        performance.mark('cpu-check-end');
        performance.measure('cpu-check', 'cpu-check-start', 'cpu-check-end');

        const measure = performance.getEntriesByName('cpu-check')[0];
        const duration = measure.duration;

        // Cleanup
        performance.clearMarks();
        performance.clearMeasures();

        // Estimate CPU usage based on how long the operation took
        const expectedDuration = 5; // ms
        const cpuEstimate = Math.min(100, (duration / expectedDuration) * 20);

        return Math.round(cpuEstimate);
      } catch (error) {
        logger.error('Failed to estimate CPU usage:', error);
        return 0;
      }
    }

    return 0;
  }

  private getMemoryUsage(): number {
    // Check if memory API is available (Chrome)
    if ('memory' in performance) {
      const memory = (performance as any).memory;
      if (memory.usedJSHeapSize && memory.jsHeapSizeLimit) {
        return (memory.usedJSHeapSize / memory.jsHeapSizeLimit) * 100;
      }
    }

    // Fallback: estimate based on array sizes
    const estimatedBytes =
      this.latencyHistory.length * 8 + // numbers
      this.bytesHistory.length * 16 +  // objects
      1024 * 1024; // base overhead

    const estimatedMB = estimatedBytes / (1024 * 1024);
    // Assume 2GB heap limit
    return Math.min(100, (estimatedMB / 2048) * 100);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Diagnostics Management
  // ─────────────────────────────────────────────────────────────────────────

  private startDiagnostics(): void {
    this.diagnosticsInterval = setInterval(() => {
      const diagnostics = this.analyze();

      // Update store
      const store = useWSEStore.getState();
      store.updateDiagnostics(diagnostics);

      // Log if quality is poor
      if (diagnostics.quality === ConnectionQuality.POOR) {
        logger.warn('Poor connection quality detected:', diagnostics);
      }
    }, this.diagnosticsIntervalMs);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Public API
  // ─────────────────────────────────────────────────────────────────────────

  getLastDiagnostics(): NetworkDiagnostics | null {
    return this.lastDiagnostics;
  }

  getLatencyStats(): {
    current: number | null;
    average: number;
    min: number | null;
    max: number | null;
    jitter: number;
  } {
    const current = this.latencyHistory[this.latencyHistory.length - 1] || null;
    const average = this.calculateAverage(this.latencyHistory);
    const min = this.latencyHistory.length > 0 ? Math.min(...this.latencyHistory) : null;
    const max = this.latencyHistory.length > 0 ? Math.max(...this.latencyHistory) : null;
    const jitter = this.calculateJitter();

    return { current, average, min, max, jitter };
  }

  reset(): void {
    this.latencyHistory = [];
    this.packetsSent = 0;
    this.packetsReceived = 0;
    this.bytesHistory = [];
    this.lastDiagnostics = null;
  }

  destroy(): void {
    if (this.diagnosticsInterval) {
      clearInterval(this.diagnosticsInterval);
      this.diagnosticsInterval = null;
    }
    this.reset();
  }
}