import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  buildInitialSnapshot,
  applySnapshot,
  applySegmentEvent,
  applyRefinedSegmentEvent,
  applySuppressedSegmentEvent,
  applyHealthEvent,
  applyFormulaEvent,
} from './sessionReducer';
import {
  createMockSegment,
  createMockPartialSegment,
  createMockSuppressedSegment,
  createMockReviewSegment,
  createMockFormula,
  createMockHealth,
  createMockSnapshot,
  createMockSessionSummary,
} from '../test/factories';

describe('sessionReducer', () => {
  describe('buildInitialSnapshot', () => {
    it('creates initial snapshot with default values', () => {
      const snapshot = buildInitialSnapshot();

      expect(snapshot.session).toBeNull();
      expect(snapshot.transcript).toEqual([]);
      expect(snapshot.formulas).toEqual([]);
      expect(snapshot.needs_review).toEqual([]);
      expect(snapshot.health.audio_stream_active).toBe(false);
      expect(snapshot.available_models).toContain('small');
      expect(snapshot.available_languages).toContain('en');
    });

    it('has runtime revision of 0', () => {
      const snapshot = buildInitialSnapshot();
      expect(snapshot.runtime_revision).toBe(0);
    });

    it('has loading set to false', () => {
      const snapshot = buildInitialSnapshot();
      expect(snapshot.loading).toBe(false);
    });
  });

  describe('applySnapshot', () => {
    it('applies partial snapshot updates', () => {
      const current = buildInitialSnapshot();
      const update = {
        session: createMockSessionSummary(),
        runtime_revision: 1,
      };

      const result = applySnapshot(current, update);

      expect(result.session).toEqual(update.session);
      expect(result.runtime_revision).toBe(1);
      expect(result.transcript).toEqual(current.transcript);
    });

    it('merges transcript arrays', () => {
      const current = buildInitialSnapshot();
      const newTranscript = [createMockSegment({ id: '1', text: 'Test' })];
      const update = { transcript: newTranscript };

      const result = applySnapshot(current, update);

      expect(result.transcript).toEqual(newTranscript);
    });

    it('syncs session counts after update', () => {
      const current = buildInitialSnapshot();
      const segments = [
        createMockSegment({ id: '1' }),
        createMockSegment({ id: '2' }),
      ];
      const update = {
        session: createMockSessionSummary(),
        transcript: segments,
      };

      const result = applySnapshot(current, update);

      expect(result.session?.segment_count).toBe(2);
    });

    it('handles null session gracefully', () => {
      const current = buildInitialSnapshot();
      const update = { session: null };

      const result = applySnapshot(current, update);

      expect(result.session).toBeNull();
    });
  });

  describe('applySegmentEvent', () => {
    it('adds new segment to transcript', () => {
      const current = buildInitialSnapshot();
      const segment = createMockSegment({ id: 'new-seg', text: 'New segment' });

      const result = applySegmentEvent(current, segment);

      expect(result.transcript).toHaveLength(1);
      expect(result.transcript[0].text).toBe('New segment');
    });

    it('updates existing segment by ID', () => {
      const current = buildInitialSnapshot();
      const segment1 = createMockSegment({ id: 'seg-1', text: 'Original' });
      const currentWithSeg = applySegmentEvent(current, segment1);

      const segment2 = createMockSegment({ id: 'seg-1', text: 'Updated' });
      const result = applySegmentEvent(currentWithSeg, segment2);

      expect(result.transcript).toHaveLength(1);
      expect(result.transcript[0].text).toBe('Updated');
    });

    it('removes partial segments when final arrives', () => {
      const current = buildInitialSnapshot();
      const partial = createMockPartialSegment({ id: 'partial-1' });
      const currentWithPartial = applySegmentEvent(current, partial);

      const final = createMockSegment({ id: 'final-1', is_partial: false });
      const result = applySegmentEvent(currentWithPartial, final);

      const partials = result.transcript.filter(s => s.is_partial);
      expect(partials).toHaveLength(0);
    });

    it('adds review flagged segments to needs_review', () => {
      const current = buildInitialSnapshot();
      const reviewSegment = createMockReviewSegment({ id: 'review-1' });

      const result = applySegmentEvent(current, reviewSegment);

      expect(result.needs_review).toHaveLength(1);
      expect(result.needs_review[0].id).toBe('review-1');
    });

    it('deduplicates needs_review array', () => {
      const current = buildInitialSnapshot();
      const reviewSegment = createMockReviewSegment({ id: 'review-1' });

      const result1 = applySegmentEvent(current, reviewSegment);
      const result2 = applySegmentEvent(result1, reviewSegment);

      expect(result2.needs_review).toHaveLength(1);
    });

    it('limits transcript size to 500 segments', () => {
      const current = buildInitialSnapshot();
      let result = current;

      // Add more than 500 segments
      for (let i = 0; i < 550; i++) {
        result = applySegmentEvent(result, createMockSegment({ id: `seg-${i}` }));
      }

      expect(result.transcript.length).toBeLessThanOrEqual(500);
    });

    it('updates an existing segment when refinement arrives', () => {
      const current = buildInitialSnapshot();
      const original = createMockSegment({ id: 'seg-1', text: 'project status update', display_text: 'project status update' });
      const withOriginal = applySegmentEvent(current, original);

      const refined = createMockSegment({
        id: 'seg-1',
        text: 'project status update',
        display_text: 'Project status update.',
        raw_text: 'project status update',
        refined_text: 'Project status update.',
        was_refined: true,
      });

      const result = applyRefinedSegmentEvent(withOriginal, refined);

      expect(result.transcript).toHaveLength(1);
      expect(result.transcript[0].display_text).toBe('Project status update.');
      expect(result.transcript[0].was_refined).toBe(true);
    });
  });

  describe('applySuppressedSegmentEvent', () => {
    it('adds segment to suppressed_transcript', () => {
      const current = buildInitialSnapshot();
      const segment = createMockSuppressedSegment({ id: 'sup-1' });

      const result = applySuppressedSegmentEvent(current, segment);

      expect(result.suppressed_transcript).toHaveLength(1);
      expect(result.suppressed_transcript[0].id).toBe('sup-1');
    });

    it('adds review flagged suppressed segments to needs_review', () => {
      const current = buildInitialSnapshot();
      const segment = createMockSuppressedSegment({
        id: 'sup-review-1',
        review_flag: true,
        review_reasons: ['test'],
      });

      const result = applySuppressedSegmentEvent(current, segment);

      expect(result.needs_review).toHaveLength(1);
    });

    it('limits suppressed transcript size', () => {
      const current = buildInitialSnapshot();
      let result = current;

      // Add many suppressed segments
      for (let i = 0; i < 250; i++) {
        result = applySuppressedSegmentEvent(result, createMockSuppressedSegment({ id: `sup-${i}` }));
      }

      expect(result.suppressed_transcript.length).toBeLessThanOrEqual(200);
    });
  });

  describe('applyHealthEvent', () => {
    it('updates health data', () => {
      const current = buildInitialSnapshot();
      const health = createMockHealth({ gpu_mode: 'cuda', queue_depth: 5 });

      const result = applyHealthEvent(current, { health, meter_value: 0.75 });

      expect(result.health.gpu_mode).toBe('cuda');
      expect(result.health.queue_depth).toBe(5);
      expect(result.meter_value).toBe(0.75);
    });

    it('preserves existing transcript data', () => {
      const current = buildInitialSnapshot();
      const currentWithSegment = applySegmentEvent(current, createMockSegment());
      const health = createMockHealth();

      const result = applyHealthEvent(currentWithSegment, { health, meter_value: 0.5 });

      expect(result.transcript).toHaveLength(1);
    });
  });

  describe('applyFormulaEvent', () => {
    it('adds formulas to the formulas array', () => {
      const current = buildInitialSnapshot();
      const formulas = [
        createMockFormula({ expression: 'E = mc^2' }),
        createMockFormula({ expression: 'F = ma' }),
      ];

      const result = applyFormulaEvent(current, formulas);

      expect(result.formulas).toHaveLength(2);
    });

    it('replaces existing formulas', () => {
      const current = createMockSnapshot({
        formulas: [createMockFormula({ expression: 'Old formula' })],
      });
      const newFormulas = [createMockFormula({ expression: 'New formula' })];

      const result = applyFormulaEvent(current, newFormulas);

      expect(result.formulas).toHaveLength(1);
      expect(result.formulas[0].expression).toBe('New formula');
    });

    it('limits formulas to 200 items', () => {
      const current = buildInitialSnapshot();
      const manyFormulas = Array.from({ length: 250 }, (_, i) =>
        createMockFormula({ expression: `Formula ${i}` })
      );

      const result = applyFormulaEvent(current, manyFormulas);

      expect(result.formulas.length).toBeLessThanOrEqual(200);
    });

    it('syncs formula count in session', () => {
      const current = buildInitialSnapshot();
      const currentWithSession = applySnapshot(current, {
        session: createMockSessionSummary(),
      });
      const formulas = [
        createMockFormula({ expression: 'Test 1' }),
        createMockFormula({ expression: 'Test 2' }),
      ];

      const result = applyFormulaEvent(currentWithSession, formulas);

      expect(result.session?.formula_count).toBe(2);
    });
  });

  describe('integration scenarios', () => {
    it('handles full transcription flow', () => {
      let state = buildInitialSnapshot();

      // Start session
      state = applySnapshot(state, {
        session: createMockSessionSummary({ status: 'running' }),
      });

      // Add partial segment
      const partial = createMockPartialSegment({ text: 'Hello...' });
      state = applySegmentEvent(state, partial);

      expect(state.transcript).toHaveLength(1);
      expect(state.transcript[0].is_partial).toBe(true);

      // Finalize segment
      const final = createMockSegment({ text: 'Project status update', is_partial: false });
      state = applySegmentEvent(state, final);

      expect(state.transcript[0].is_partial).toBe(false);
      expect(state.transcript[0].text).toBe('Project status update');

      // Update health
      state = applyHealthEvent(state, {
        health: createMockHealth({ audio_stream_active: true }),
        meter_value: 0.8,
      });

      expect(state.health.audio_stream_active).toBe(true);
      expect(state.meter_value).toBe(0.8);
    });

    it('handles review workflow', () => {
      let state = buildInitialSnapshot();
      state = applySnapshot(state, {
        session: createMockSessionSummary(),
      });

      // Add normal segment
      const normal = createMockSegment({ id: 'normal-1', text: 'Normal text' });
      state = applySegmentEvent(state, normal);

      expect(state.needs_review).toHaveLength(0);

      // Add segment that needs review
      const needsReview = createMockReviewSegment({ id: 'review-1', text: 'Formula: E=mc^2' });
      state = applySegmentEvent(state, needsReview);

      expect(state.needs_review).toHaveLength(1);
      expect(state.session?.review_count).toBe(1);

      // Add formula
      const formulas = [createMockFormula({ expression: 'E = mc^2' })];
      state = applyFormulaEvent(state, formulas);

      expect(state.session?.formula_count).toBe(1);
    });

    it('handles suppression workflow', () => {
      let state = buildInitialSnapshot();
      state = applySnapshot(state, {
        session: createMockSessionSummary(),
      });

      // Add suppressed segment
      const suppressed = createMockSuppressedSegment({
        id: 'sup-1',
        text: 'Um uh um',
        suppression_reasons: ['filler'],
      });
      state = applySuppressedSegmentEvent(state, suppressed);

      expect(state.suppressed_transcript).toHaveLength(1);
      expect(state.transcript).toHaveLength(0);
      expect(state.session?.suppressed_count).toBe(1);
    });
  });
});
