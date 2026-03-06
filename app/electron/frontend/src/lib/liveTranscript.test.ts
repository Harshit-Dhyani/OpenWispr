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
      text: 'project status update',
      start: 0,
      end: 1,
      committed_text: 'project',
      draft_suffix: 'status update',
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
      text: 'project status update',
      start: 0,
      end: 1,
      committed_text: '',
      draft_suffix: 'project status update',
    });

    const staleCommit = {
      session_id: 'session-b',
      segment_id: 'seg-1',
      revision: 2,
      stream_id: 'stream-1',
      text: 'project status update',
      start: 0,
      end: 1,
      committed_text: 'project status update',
      draft_suffix: '',
      segment: createMockSegment({ id: 'seg-1', text: 'project status update' }),
    };
    const activeCommit = {
      ...staleCommit,
      session_id: 'session-a',
    };

    expect(clearLiveDraftForCommit(draft, 'session-a', staleCommit)).toEqual(draft);
    expect(clearLiveDraftForCommit(draft, 'session-a', activeCommit)).toBeNull();
  });

  it('maintains replace semantics across mixed draft and commit ordering', () => {
    const activeSessionId = 'session-a';
    let current = null as ReturnType<typeof buildStructuredLiveDraft> | null;

    const activeDraft = (revision: number, text: string, committed = '', draftSuffix = text) =>
      buildStructuredLiveDraft({
        session_id: activeSessionId,
        segment_id: 'seg-1',
        revision,
        stream_id: 'stream-1',
        text,
        start: 0,
        end: 1,
        committed_text: committed,
        draft_suffix: draftSuffix,
      });

    const makeCommit = (sessionId: string, revision: number, text: string) => ({
      session_id: sessionId,
      segment_id: 'seg-1',
      revision,
      stream_id: 'stream-1',
      text,
      start: 0,
      end: 1,
      committed_text: text,
      draft_suffix: '',
      segment: createMockSegment({ id: 'seg-1', text }),
    });

    current = activeDraft(1, 'project');
    expect(current?.draftSuffix).toBe('project');

    current = activeDraft(2, 'project status update', 'project', 'status update');
    expect(current?.committedText).toBe('project');
    expect(current?.draftSuffix).toBe('status update');

    current = clearLiveDraftForCommit(current, activeSessionId, makeCommit('session-b', 3, 'stale'));
    expect(current?.draftSuffix).toBe('status update');

    current = clearLiveDraftForCommit(current, activeSessionId, makeCommit(activeSessionId, 4, 'project status update'));
    expect(current).toBeNull();

    current = activeDraft(5, 'next chunk');
    expect(current?.draftSuffix).toBe('next chunk');
  });
});
