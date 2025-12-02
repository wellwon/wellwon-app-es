// System status store for health monitoring
import { create } from 'zustand';

// Detailed system status for health dashboard
interface DetailedSystemStatus {
  api?: string;
  api_status?: string;
  datafeed_status?: string;
  redis?: string;
  event_bus?: string;
  cpu_usage?: number;
  memory_usage?: number;
  lastBackup?: string;
  active_connections?: number;
  event_queue_size?: number;
  adapter_statuses?: Record<string, string>;
  module_statuses?: Record<string, string>;
  circuit_breakers?: Record<string, string>;
  uptime?: number;
}

interface SystemStatusState {
  status: 'online' | 'offline' | 'maintenance';
  details: DetailedSystemStatus | null;
  lastCheck: number;
  setStatus: (status: 'online' | 'offline' | 'maintenance' | DetailedSystemStatus) => void;
}

export const useSystemStatusStore = create<SystemStatusState>((set) => ({
  status: 'online',
  details: null,
  lastCheck: Date.now(),
  setStatus: (status) => {
    if (typeof status === 'string') {
      set({ status, lastCheck: Date.now() });
    } else {
      // Detailed status object - derive simple status from API status
      const simpleStatus = status.api_status === 'healthy' || status.api === 'healthy'
        ? 'online'
        : status.api_status === 'maintenance'
        ? 'maintenance'
        : 'online'; // default to online
      set({ status: simpleStatus, details: status, lastCheck: Date.now() });
    }
  },
}));

export default useSystemStatusStore;
