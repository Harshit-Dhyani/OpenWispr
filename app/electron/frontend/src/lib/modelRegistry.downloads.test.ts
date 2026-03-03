import { describe, expect, it } from 'vitest';
import { applyModelDownloadEvent, EMPTY_MODEL_MANAGER_STATE } from './modelRegistry';

describe('modelRegistry download progress', () => {
  it('keeps progress monotonic for the same download attempt', () => {
    const started = applyModelDownloadEvent(EMPTY_MODEL_MANAGER_STATE, 'model-download-started', {
      model_id: 'whisper-medium',
      download_id: 'attempt-1',
      attempt: 1,
      status: 'downloading',
      bytes_downloaded: 100,
      total_bytes: 1000,
      total_bytes_known: true,
      progress: 25,
      speed_bytes_per_sec: 50,
      error: null,
    });

    const regressed = applyModelDownloadEvent(started, 'model-download-progress', {
      model_id: 'whisper-medium',
      download_id: 'attempt-1',
      attempt: 1,
      status: 'downloading',
      bytes_downloaded: 90,
      total_bytes: 1000,
      total_bytes_known: true,
      progress: 10,
      speed_bytes_per_sec: 40,
      error: null,
    });

    expect(regressed.downloads['whisper-medium']).toMatchObject({
      bytes_downloaded: 100,
      progress: 25,
    });
  });

  it('ignores stale progress from an older download attempt', () => {
    const current = applyModelDownloadEvent(EMPTY_MODEL_MANAGER_STATE, 'model-download-started', {
      model_id: 'whisper-medium',
      download_id: 'attempt-2',
      attempt: 2,
      status: 'downloading',
      bytes_downloaded: 50,
      total_bytes: 0,
      total_bytes_known: false,
      progress: 0,
      speed_bytes_per_sec: 10,
      error: null,
    });

    const stale = applyModelDownloadEvent(current, 'model-download-progress', {
      model_id: 'whisper-medium',
      download_id: 'attempt-1',
      attempt: 1,
      status: 'downloading',
      bytes_downloaded: 500,
      total_bytes: 1000,
      total_bytes_known: true,
      progress: 50,
      speed_bytes_per_sec: 100,
      error: null,
    });

    expect(stale.downloads['whisper-medium']).toMatchObject({
      download_id: 'attempt-2',
      bytes_downloaded: 50,
      progress: 0,
    });
  });

  it('resets cleanly into retrying state for a new attempt', () => {
    const started = applyModelDownloadEvent(EMPTY_MODEL_MANAGER_STATE, 'model-download-started', {
      model_id: 'whisper-medium',
      download_id: 'attempt-1',
      attempt: 1,
      status: 'downloading',
      bytes_downloaded: 400,
      total_bytes: 1000,
      total_bytes_known: true,
      progress: 40,
      speed_bytes_per_sec: 80,
      error: null,
    });

    const retried = applyModelDownloadEvent(started, 'model-download-retrying', {
      model_id: 'whisper-medium',
      download_id: 'attempt-2',
      attempt: 2,
      status: 'retrying',
      bytes_downloaded: 0,
      total_bytes: 0,
      total_bytes_known: false,
      progress: 0,
      speed_bytes_per_sec: 0,
      error: 'network reset',
    });

    expect(retried.downloads['whisper-medium']).toMatchObject({
      download_id: 'attempt-2',
      attempt: 2,
      status: 'retrying',
      bytes_downloaded: 0,
      progress: 0,
      total_bytes_known: false,
    });
  });
});
