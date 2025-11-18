// =============================================================================
// File: src/wse/index.ts
// Description: WebSocket Event System public exports
// =============================================================================

// ─────────────────────────────────────────────────────────────────────────────
// Main Hook
// ─────────────────────────────────────────────────────────────────────────────

export { useWSE } from './hooks/useWSE';
export { useWSEQuery, useWSEMutation } from './hooks/useWSEQuery';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export * from './types';

// ─────────────────────────────────────────────────────────────────────────────
// Stores
// ─────────────────────────────────────────────────────────────────────────────

export { useWSEStore } from './stores/useWSEStore';
export { useMessageQueueStore } from './stores/useMessageQueueStore';

// ─────────────────────────────────────────────────────────────────────────────
// Utils
// ─────────────────────────────────────────────────────────────────────────────

export { logger, Logger, LogLevel } from './utils/logger';
export { CircuitBreaker, createCircuitBreaker } from './utils/circuitBreaker';
export { PriorityQueue } from './utils/priorityQueue';
export { EventSequencer } from './services/EventSequencer';
export { AdaptiveQualityManager } from './services/AdaptiveQualityManager';
export { compressionManager } from './protocols/compression';
export { eventTransformer } from './protocols/transformer';

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

export * from './constants';

// ─────────────────────────────────────────────────────────────────────────────
// Version Info
// ─────────────────────────────────────────────────────────────────────────────

export const WSE_VERSION = '2.0.0';
export const WSE_PROTOCOL_VERSION = 2;