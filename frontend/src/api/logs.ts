// File: src/api/logs.ts

import { API } from './core';

export interface BrowserLog {
  timestamp: string;
  request: string;
  response: string;
}

export async function fetchLogs(): Promise<BrowserLog[]> {
  const { data } = await API.get<BrowserLog[]>('/logs');
  return data;
}