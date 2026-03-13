import type { CommitFinalPayload, DraftPartialPayload } from '../types/api';

export type LiveDraftState = {
  sessionId: string | null;
  committedText: string;
  draftSuffix: string;
  revision: number;
  source: 'structured' | 'legacy';
};

export function isEventForActiveSession(
  activeSessionId: string | null | undefined,
  eventSessionId: string | null | undefined,
): boolean {
  if (!eventSessionId) {
    return true;
  }
  return Boolean(activeSessionId) && activeSessionId === eventSessionId;
}

export function buildStructuredLiveDraft(payload: DraftPartialPayload): LiveDraftState {
  return {
    sessionId: payload.session_id,
    committedText: payload.committed_text,
    draftSuffix: payload.draft_suffix,
    revision: payload.revision,
    source: 'structured',
  };
}

export function shouldIgnoreLegacyPartial(
  current: LiveDraftState | null,
  activeSessionId: string | null | undefined,
): boolean {
  return Boolean(
    current?.source === 'structured' &&
      current.sessionId &&
      activeSessionId &&
      current.sessionId === activeSessionId,
  );
}

export function clearLiveDraftForCommit(
  current: LiveDraftState | null,
  activeSessionId: string | null | undefined,
  payload: CommitFinalPayload,
): LiveDraftState | null {
  if (!isEventForActiveSession(activeSessionId, payload.session_id)) {
    return current;
  }
  return null;
}
