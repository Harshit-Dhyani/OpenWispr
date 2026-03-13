import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { HomePage } from '../HomePage';
import type { HistoryAnalytics, HistorySession } from '../../types/api';

describe('HomePage', () => {
  it('keeps copy transcript as the first action button on each session card', async () => {
    const sessions: HistorySession[] = [
      {
        session_id: 's-1',
        source_workflow: 'hotkey',
        capture_source: 'microphone',
        model_name: 'whisper-medium',
        active_text: 'first transcript',
        active_text_source: 'postprocessed_text',
        word_count: 2,
        started_at: '2026-03-05T00:00:00Z',
        ended_at: '2026-03-05T00:00:03Z',
        audio_available: true,
        retry_status: 'idle',
        retry_attempt_count: 0,
      },
    ];

    const analytics: HistoryAnalytics = {
      summary: {
        days_used: 1,
        total_words: 2,
        avg_wpm: 80,
        peak_usage_hour: 10,
      },
      daily: [{ day: '2026-03-05', count: 1 }],
      hourly: [{ hour: 10, count: 1 }],
    };

    const request = vi.fn(async <T,>(path: string): Promise<T> => {
      if (path.startsWith('/api/history/analytics')) {
        return analytics as T;
      }
      return { sessions } as T;
    });

    render(
      <HomePage
        request={request}
        onOpenSettings={vi.fn()}
        onStatus={vi.fn()}
        defaultRangeDays={7}
        allowRetry
        persistAudio
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('first transcript')).toBeInTheDocument();
    });

    const card = screen.getByText('first transcript').closest('article');
    expect(card).not.toBeNull();
    const buttons = within(card as HTMLElement).getAllByRole('button');
    expect(buttons[0]).toHaveTextContent('Copy transcript');

    expect(request).toHaveBeenCalledWith('/api/history/analytics?range_days=7');
    expect(request).toHaveBeenCalledWith('/api/history/sessions?range_days=7&limit=250');
  });
});

