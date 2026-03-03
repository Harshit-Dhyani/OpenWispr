import { describe, expect, it } from 'vitest';
import {
  buildStructuredLiveDraft,
  clearLiveDraftForCommit,
  isEventForActiveSession,
  shouldIgnoreLegacyPartial,
} from './liveTranscript';
import { createMockSegment } from '../test/factories';

describe('liveTranscript', () => {
  it('accepts only events from the active session', () => {
    expect(isEventForActiveSession('session-a', 'session-a')).toBe(true);
    expect(isEventForActiveSession('session-a', 'session-b')).toBe(false);
    expect(isEventForActiveSession('session-a', null)).toBe(true);
    expect(isEventForActiveSession(null, 'session-a')).toBe(false);
  });

  it('ignores legacy partials after structured draft events for the active session', () => {
    const draft = buildStructuredLiveDraft({
      session_id: 'session-a',
      segment_id: 'seg-1',
      revision: 3,
      stream_id: 'stream-1',
      text: 'hello world',
      start: 0,
      end: 1,
      committed_text: 'hello',
      draft_suffix: 'world',
    });

    expect(shouldIgnoreLegacyPartial(draft, 'session-a')).toBe(true);
    expect(shouldIgnoreLegacyPartial(draft, 'session-b')).toBe(false);
  });

  it('clears live draft only for matching commit events', () => {
    const draft = buildStructuredLiveDraft({
      session_id: 'session-a',
      segment_id: 'seg-1',
      revision: 1,
      stream_id: 'stream-1',
      text: 'hello world',
      start: 0,
      end: 1,
      committed_text: '',
      draft_suffix: 'hello world',
    });

    const staleCommit = {
      session_id: 'session-b',
      segment_id: 'seg-1',
      revision: 2,
      stream_id: 'stream-1',
      text: 'hello world',
      start: 0,
      end: 1,
      committed_text: 'hello world',
      draft_suffix: '',
      segment: createMockSegment({ id: 'seg-1', text: 'hello world' }),
    };
    const activeCommit = {
      ...staleCommit,
      session_id: 'session-a',
    };

    expect(clearLiveDraftForCommit(draft, 'session-a', staleCommit)).toEqual(draft);
    expect(clearLiveDraftForCommit(draft, 'session-a', activeCommit)).toBeNull();
  });
});
