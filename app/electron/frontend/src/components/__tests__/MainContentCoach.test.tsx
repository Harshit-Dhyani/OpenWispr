import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MainContent } from '../MainContent';
import { createMockSegment, createMockSnapshot } from '../../test/factories';

describe('MainContent coach panel', () => {
  it('shows polished coach output for dictation stops', () => {
    render(
      <MainContent
        scope="dictation"
        snapshot={createMockSnapshot({
          transcript: [],
          needs_review: [],
          formulas: [],
          suppressed_transcript: [],
        })}
        coachStatus="generated"
        coachResult={{
          original: 'i want to improve my english writing',
          polished: 'I want to improve my English writing.',
          diff: [],
          tips: ['Capitalize the pronoun "I".'],
          mistakes: [
            {
              type: 'grammar',
              example: 'i',
              fix: 'I',
              why: 'The first-person pronoun is always capitalized.',
            },
          ],
          practice: {
            prompt: 'Rewrite it more clearly.',
            answer: 'I want to improve my English writing.',
          },
          meta: {
            model: 'none',
            confidence: 0,
            cache_hit: false,
            provider: 'disabled_local_only',
            prompt_template_id: 'default_english_coach',
            prompt_version: 1,
          },
        }}
        originalText="i want to improve my english writing"
        pasteText="I want to improve my English writing."
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /show inspector/i }));
    fireEvent.click(screen.getByRole('button', { name: /coach/i }));

    expect(screen.getByText('Coach Result')).toBeInTheDocument();
    expect(screen.getAllByText('I want to improve my English writing.').length).toBeGreaterThan(0);
    expect(screen.getByText('Capitalize the pronoun "I".')).toBeInTheDocument();
    expect(screen.getByText('Original')).toBeInTheDocument();
  });

  it('renders fallback transcript output as fallback instead of a generated coach result', () => {
    render(
      <MainContent
        scope="dictation"
        snapshot={createMockSnapshot({
          transcript: [],
          needs_review: [],
          formulas: [],
          suppressed_transcript: [],
        })}
        coachStatus="fallback"
        coachResult={null}
        coachDisplaySource="fallback"
        originalText="hello there this is the final transcript"
        pasteText="hello there this is the final transcript"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /show inspector/i }));
    fireEvent.click(screen.getByRole('button', { name: /coach/i }));

    expect(screen.getByText('Fallback Output')).toBeInTheDocument();
    expect(screen.getByText('fallback')).toBeInTheDocument();
    expect(screen.getByText(/deterministic fallback output/i)).toBeInTheDocument();
    expect(screen.queryByText('Coach Failed')).not.toBeInTheDocument();
    expect(screen.queryByText('Tips')).not.toBeInTheDocument();
    expect(screen.getAllByText('hello there this is the final transcript').length).toBeGreaterThanOrEqual(2);
  });

  it('shows a combined dictation panel with merged live transcript text', () => {
    render(
      <MainContent
        scope="dictation"
        snapshot={createMockSnapshot({
          transcript: [
            createMockSegment({ id: 's1', text: 'first line', display_text: 'first line', words: [] }),
            createMockSegment({ id: 's2', text: 'second line', display_text: 'second line', words: [] }),
          ],
          needs_review: [],
          formulas: [],
          suppressed_transcript: [],
        })}
        liveDraft={{ committedText: 'third line', draftSuffix: 'tail' }}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /show inspector/i }));
    fireEvent.click(screen.getByRole('button', { name: /combined/i }));

    expect(screen.getByText('Combined Dictation')).toBeInTheDocument();
    expect(screen.getAllByText('first line second line third line tail')).toHaveLength(2);
  });

  it('renders coach diff operations when diff view is enabled', () => {
    render(
      <MainContent
        scope="dictation"
        snapshot={createMockSnapshot({
          transcript: [],
          needs_review: [],
          formulas: [],
          suppressed_transcript: [],
        })}
        showCoachDiff
        coachStatus="generated"
        coachResult={{
          original: 'hello',
          polished: 'hello there',
          diff: [
            { op: 'replace', from: 'hello', to: 'hello there', start: 0, end: 5 },
          ],
          tips: [],
          mistakes: [],
          practice: { prompt: '', answer: '' },
          meta: {
            model: 'none',
            confidence: 0,
            cache_hit: false,
            provider: 'local_llm',
            prompt_template_id: 'default_english_coach',
            prompt_version: 1,
          },
        }}
        originalText="hello"
        pasteText="hello there"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /show inspector/i }));
    fireEvent.click(screen.getByRole('button', { name: /coach/i }));

    expect(screen.getByText('Edit Diff')).toBeInTheDocument();
    expect(screen.getByText('Replace')).toBeInTheDocument();
    expect(screen.getByText(/^From:/)).toBeInTheDocument();
    expect(screen.getByText(/^To:/)).toBeInTheDocument();
  });
});
