/**
 * healthService.ts - Unified Health Query Layer
 */

import type { Health } from '../types/api';

const API_BASE = 'http://127.0.0.1:8765';
const CACHE_TTL = 5000;

const defaultHealth: Health = {
  audio_stream_active: false,
  gpu_mode: 'unknown',
  execution_mode: 'auto',
  model_runtime_device: 'unknown',
  last_transcript_at: null,
  dropped_frames: 0,
  queue_depth: 0,
  dropped_stt_chunks: 0,
  stt_backpressure_state: 'normal',
  estimated_backlog_seconds: 0,
  last_error: null,
  last_warning: null,
};

let healthCache: Health | null = null;
let lastFetchTime = 0;

export async function getHealth(): Promise<{ health: Health; isAvailable: boolean; lastError: string | null }> {
  const now = Date.now();
  
  if (healthCache && now - lastFetchTime < CACHE_TTL) {
    return { health: healthCache, isAvailable: true, lastError: null };
  }

  try {
    const response = await fetch(`${API_BASE}/api/session`);
    if (!response.ok) throw new Error('Failed to fetch');
    
    const data = await response.json();
    const health = { ...defaultHealth, ...data.health };
    healthCache = health;
    lastFetchTime = now;
    
    return { health, isAvailable: true, lastError: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to fetch health';
    return { health: defaultHealth, isAvailable: false, lastError: message };
  }
}

export function invalidateHealthCache(): void {
  healthCache = null;
  lastFetchTime = 0;
}
