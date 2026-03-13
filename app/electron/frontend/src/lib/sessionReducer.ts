import type { Formula, Health, Segment, SnapshotPayload } from '../types/api';

const MAX_TRANSCRIPT_SEGMENTS = 500;
const MAX_SUPPRESSED_SEGMENTS = 200;
const MAX_FORMULAS = 200;
const MAX_REVIEW = 200;

function dedupeById<T extends { id: string }>(items: T[], limit: number): T[] {
  const seen = new Set<string>();
  const result: T[] = [];
  for (let index = items.length - 1; index >= 0; index -= 1) {
    const item = items[index];
    if (seen.has(item.id)) {
      continue;
    }
    seen.add(item.id);
    result.push(item);
    if (result.length >= limit) {
      break;
    }
  }
  return result.reverse();
}

function mergeSegment(list: Segment[], segment: Segment, limit: number): Segment[] {
  const withoutSameId = list.filter((item) => item.id !== segment.id);
  return dedupeById([...withoutSameId, segment], limit);
}

function normalizeReviewSegments(segments: Segment[]): Segment[] {
  return dedupeById(segments.filter((segment) => segment.review_flag), MAX_REVIEW);
}

function syncSessionCounts(snapshot: SnapshotPayload): SnapshotPayload {
  if (!snapshot.session) {
    return snapshot;
  }
  return {
    ...snapshot,
    session: {
      ...snapshot.session,
      segment_count: snapshot.transcript.filter((segment) => !segment.suppressed && !segment.is_partial)
        .length,
      formula_count: snapshot.formulas.length,
      review_count: snapshot.needs_review.length,
      suppressed_count: snapshot.suppressed_transcript.length,
    },
  };
}

export function buildInitialSnapshot(): SnapshotPayload {
  return {
    session: null,
    transcript: [],
    formulas: [],
    needs_review: [],
    health: {
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
    },
    meter_value: 0,
    available_models: ['tiny', 'base', 'small', 'medium', 'large-v3'],
    available_languages: ['auto', 'en', 'hi', 'ur', 'bn', 'ta', 'te', 'mr', 'gu', 'pa', 'ar', 'fr', 'de', 'es', 'pt', 'it', 'nl', 'tr', 'ru', 'uk', 'pl', 'ja', 'ko', 'zh', 'id', 'vi', 'th'],
    available_live_modes: ['realtime', 'low_latency', 'balanced', 'high_accuracy'],
    available_execution_modes: ['auto', 'gpu_only', 'cpu_only'],
    suppressed_transcript: [],
    runtime_revision: 0,
    loading: false,
    loading_message: '',
    model_cache: {},
  };
}

export function applySnapshot(
  current: SnapshotPayload,
  payload: Partial<SnapshotPayload>,
): SnapshotPayload {
  const next: SnapshotPayload = {
    ...current,
    ...payload,
    transcript: payload.transcript ?? current.transcript,
    suppressed_transcript: payload.suppressed_transcript ?? current.suppressed_transcript,
    formulas: payload.formulas ?? current.formulas,
    needs_review: payload.needs_review ?? current.needs_review,
    health: payload.health ?? current.health,
    session: payload.session ?? current.session,
    model_cache: payload.model_cache ?? current.model_cache,
  };
  return syncSessionCounts(next);
}

export function applySegmentEvent(current: SnapshotPayload, segment: Segment): SnapshotPayload {
  const transcript = mergeSegment(
    current.transcript.filter((item) => !(item.is_partial && !segment.is_partial)),
    segment,
    MAX_TRANSCRIPT_SEGMENTS,
  );
  const needsReview = normalizeReviewSegments(
    segment.review_flag ? [...current.needs_review, segment] : current.needs_review,
  );
  return syncSessionCounts({
    ...current,
    transcript,
    needs_review: needsReview,
  });
}

export function applyRefinedSegmentEvent(
  current: SnapshotPayload,
  segment: Segment,
): SnapshotPayload {
  const transcript = mergeSegment(current.transcript, segment, MAX_TRANSCRIPT_SEGMENTS);
  const needsReview = normalizeReviewSegments(
    segment.review_flag
      ? [...current.needs_review.filter((item) => item.id !== segment.id), segment]
      : current.needs_review.filter((item) => item.id !== segment.id),
  );
  return syncSessionCounts({
    ...current,
    transcript,
    needs_review: needsReview,
  });
}

export function applySuppressedSegmentEvent(
  current: SnapshotPayload,
  segment: Segment,
): SnapshotPayload {
  const suppressed = mergeSegment(current.suppressed_transcript, segment, MAX_SUPPRESSED_SEGMENTS);
  const needsReview = normalizeReviewSegments(
    segment.review_flag ? [...current.needs_review, segment] : current.needs_review,
  );
  return syncSessionCounts({
    ...current,
    suppressed_transcript: suppressed,
    needs_review: needsReview,
  });
}

export function applyHealthEvent(
  current: SnapshotPayload,
  payload: { health: Health; meter_value: number },
): SnapshotPayload {
  return {
    ...current,
    health: payload.health,
    meter_value: payload.meter_value,
  };
}

export function applyFormulaEvent(current: SnapshotPayload, formulas: Formula[]): SnapshotPayload {
  const trimmed = formulas.slice(-MAX_FORMULAS);
  return syncSessionCounts({
    ...current,
    formulas: trimmed,
  });
}
