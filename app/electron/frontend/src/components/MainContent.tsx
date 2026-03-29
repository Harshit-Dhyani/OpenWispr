/**
 * MainContent - Routing container for dictation vs session content views
 * 
 * Conditionally renders DictationContent or SessionContent based on the scope prop.
 * Manages transcript state, coach results, live drafts, and debug event display for both
 * dictation and session recording modes.
 * 
 * @component
 */
import React, { useMemo } from 'react';
import type { CoachResult, Formula, Segment, SessionSummary } from '../types/api';
import { DictationContent } from './DictationContent';
import { SessionContent } from './SessionContent';

type Snapshot = {
  session: SessionSummary | null;
  transcript: Segment[];
  suppressed_transcript: Segment[];
  formulas: Formula[];
  needs_review: Segment[];
  health: {
    last_error: string | null;
    last_warning?: string | null;
    last_transcript_at: string | null;
    audio_stream_active?: boolean;
    model_runtime_device?: string | null;
  };
};

type MainContentProps = {
  scope?: 'dictation' | 'session';
  snapshot: Snapshot;
  liveLatency?: number | null;
  workspaceLabel?: string;
  workspaceTitle?: string;
  workspaceDescription?: string;
  liveDraft?: {
    committedText: string;
    draftSuffix: string;
  } | null;
  transcriptDebugEvents?: Array<{
    id: number;
    type: string;
    sessionId: string | null;
    segmentId: string | null;
    correlationId?: string | null;
    detail?: string | null;
    textLength: number;
  }>;
  coachResult?: CoachResult | null;
  coachStatus?: 'disabled' | 'queued' | 'running' | 'failed' | 'fallback' | 'cache_hit' | 'generated' | 'success' | null;
  coachDisplaySource?: 'coach' | 'fallback' | 'faithful' | null;
  coachError?: string | null;
  originalText?: string | null;
  pasteText?: string | null;
  showCoachDiff?: boolean;
};

export const MainContent = React.memo(function MainContent({
  scope = 'session',
  snapshot,
  liveLatency,
  workspaceLabel,
  workspaceTitle,
  workspaceDescription,
  liveDraft,
  transcriptDebugEvents,
  coachResult,
  coachStatus,
  coachDisplaySource,
  coachError,
  originalText,
  pasteText,
  showCoachDiff,
}: MainContentProps) {
  const dictationContentProps = useMemo(
    () => ({
      snapshot,
      liveLatency,
      workspaceLabel,
      workspaceTitle,
      workspaceDescription,
      liveDraft,
      transcriptDebugEvents,
      coachResult,
      coachStatus,
      coachDisplaySource,
      coachError,
      originalText,
      pasteText,
      showCoachDiff,
    }),
    [
      snapshot,
      liveLatency,
      workspaceLabel,
      workspaceTitle,
      workspaceDescription,
      liveDraft,
      transcriptDebugEvents,
      coachResult,
      coachStatus,
      coachDisplaySource,
      coachError,
      originalText,
      pasteText,
      showCoachDiff,
    ],
  );

  const sessionContentProps = useMemo(
    () => ({
      snapshot,
      liveLatency,
      workspaceLabel,
      workspaceTitle,
      workspaceDescription,
      liveDraft,
      transcriptDebugEvents,
    }),
    [
      snapshot,
      liveLatency,
      workspaceLabel,
      workspaceTitle,
      workspaceDescription,
      liveDraft,
      transcriptDebugEvents,
    ],
  );

  if (scope === 'dictation') {
    return <DictationContent {...dictationContentProps} />;
  }

  return <SessionContent {...sessionContentProps} />;
});
