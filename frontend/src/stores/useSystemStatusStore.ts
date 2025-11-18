// Stub store - will be replaced with proper system status monitoring
import { create } from 'zustand';

interface SystemStatusState {
  status: 'online' | 'offline' | 'maintenance';
  lastCheck: number;
  setStatus: (status: 'online' | 'offline' | 'maintenance') => void;
}

export const useSystemStatusStore = create<SystemStatusState>((set) => ({
  status: 'online',
  lastCheck: Date.now(),
  setStatus: (status) => set({ status, lastCheck: Date.now() }),
}));

export default useSystemStatusStore;
