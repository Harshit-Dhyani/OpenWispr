import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { FloatingWindow } from '../FloatingWindow';
import type { HotkeyStopResponse } from '../../types/api';

type RecordingHandler = Parameters<NonNullable<Window['openwisprFloating']>['onRecordingState']>[0];
type TranscriptHandler = Parameters<NonNullable<Window['openwisprFloating']>['onTranscription']>[0];
type AudioHandler = Parameters<NonNullable<Window['openwisprFloating']>['onAudioVisualizer']>[0];
type ModelPreparationHandler = NonNullable<Window['openwisprFloating']>['onModelPreparation'] extends (
  callback: infer T,
) => () => void
  ? T
  : never;
type CoachResultHandler = NonNullable<Window['openwisprFloating']>['onCoachResult'] extends (
  callback: infer T,
) => () => void
  ? T
  : never;
type CoachResultClearHandler = NonNullable<Window['openwisprFloating']>['onCoachResultClear'] extends (
  callback: infer T,
) => () => void
  ? T
  : never;

interface FloatingMockContext {
  recordingHandler: RecordingHandler | null;
  transcriptHandler: TranscriptHandler | null;
  audioHandler: AudioHandler | null;
  modelPreparationHandler: ModelPreparationHandler | null;
  coachResultHandler: CoachResultHandler | null;
  coachResultClearHandler: CoachResultClearHandler | null;
  cancelRecording: ReturnType<typeof vi.fn>;
  finishRecording: ReturnType<typeof vi.fn>;
  dismissResult: ReturnType<typeof vi.fn>;
}

function installFloatingMock(): FloatingMockContext {
  const context: FloatingMockContext = {
    recordingHandler: null,
    transcriptHandler: null,
    audioHandler: null,
    modelPreparationHandler: null,
    coachResultHandler: null,
    coachResultClearHandler: null,
    cancelRecording: vi.fn(),
    finishRecording: vi.fn(),
    dismissResult: vi.fn(),
  };

  Object.defineProperty(window, 'openwisprFloating', {
    writable: true,
    value: {
      onRecordingState: vi.fn((handler: RecordingHandler) => {
        context.recordingHandler = handler;
        return vi.fn();
      }),
      onTranscription: vi.fn((handler: TranscriptHandler) => {
        context.transcriptHandler = handler;
        return vi.fn();
      }),
      onAudioVisualizer: vi.fn((handler: AudioHandler) => {
        context.audioHandler = handler;
        return vi.fn();
      }),
      onCoachResult: vi.fn((handler: CoachResultHandler) => {
        context.coachResultHandler = handler;
        return vi.fn();
      }),
      onModelPreparation: vi.fn((handler: ModelPreparationHandler) => {
        context.modelPreparationHandler = handler;
        return vi.fn();
      }),
      onCoachResultClear: vi.fn((handler: CoachResultClearHandler) => {
        context.coachResultClearHandler = handler;
        return vi.fn();
      }),
      onHotkeyEvent: vi.fn(() => vi.fn()),
      cancelRecording: context.cancelRecording,
      finishRecording: context.finishRecording,
      dismissResult: context.dismissResult,
      platform: 'win32',
      strings: {
        status: {
          idle: 'Ready',
          preparing: 'Preparing',
          listening: 'Listening',
          transcribing: 'Transcribing',
          processing: 'Finishing',
          result: 'Transcript ready',
          error: 'Error',
        },
        waitingForSpeech: 'Waiting for speech...',
        actions: {
          cancel: 'Cancel',
          finish: 'Finish',
          close: 'Close',
        },
        resultMeta: {
          transcriptReady: 'Transcript ready',
          livePartialHint: 'Live transcript updates during recording.',
          sessionParagraphHint: 'Live partials stay temporary until stop.',
          genericError: 'Something went wrong.',
        },
        modelPrep: {
          title: 'Preparing speech model',
          hint: 'The first run can take longer while the model loads into memory.',
        },
      },
      debugEnabled: true,
    },
  });

  return context;
}

describe('FloatingWindow', () => {
  let now = 0;

  beforeEach(() => {
    now = 0;
    vi.spyOn(performance, 'now').mockImplementation(() => now);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('renders idle state by default', () => {
    installFloatingMock();
    render(<FloatingWindow />);

    expect(screen.getByText('Ready')).toBeInTheDocument();
    expect(screen.getByText('00:00')).toBeInTheDocument();
    expect(screen.getByText('Waiting for speech...')).toBeInTheDocument();
  });

  it('shows a loading bar while the hotkey model is preparing', () => {
    const ctx = installFloatingMock();
    render(<FloatingWindow />);

    act(() => {
      ctx.recordingHandler?.({
        isRecording: true,
        processing: false,
        finished: false,
        sessionId: 'session-warmup',
        mode: 'dictation',
      });
      ctx.modelPreparationHandler?.({
        active: true,
        stage: 'loading',
        message: 'Loading whisper-turbo model...',
        modelName: 'whisper-turbo',
        sessionId: 'session-warmup',
      });
    });

    expect(screen.getByText('Preparing')).toBeInTheDocument();
    expect(screen.getByTestId('floating-model-preparation')).toBeInTheDocument();
    expect(screen.getByText('Preparing speech model')).toBeInTheDocument();
    expect(screen.getByText('Loading whisper-turbo model...')).toBeInTheDocument();
    expect(screen.getByLabelText('Model loading progress')).toBeInTheDocument();
    expect(screen.getByText('Finish')).toBeDisabled();
  });

  it('transitions through listening, transcribing, finalizing, and done', () => {
    const ctx = installFloatingMock();
    render(<FloatingWindow />);

    act(() => {
      ctx.recordingHandler?.({
        isRecording: true,
        processing: false,
        finished: false,
        sessionId: 'session-1',
        mode: 'dictation',
      });
    });
    expect(screen.getByText('Listening')).toBeInTheDocument();

    act(() => {
      ctx.transcriptHandler?.({
        text: 'Testing a live partial',
        partialText: 'Testing a live partial',
        committedText: '',
        isPartial: true,
        sessionId: 'session-1',
        mode: 'dictation',
      });
    });
    expect(screen.getByText('Transcribing')).toBeInTheDocument();
    expect(screen.getByText('Testing a live partial')).toBeInTheDocument();

    act(() => {
      ctx.recordingHandler?.({
        isRecording: false,
        processing: true,
        finished: false,
        sessionId: 'session-1',
        mode: 'dictation',
      });
    });
    expect(screen.getByText('Finishing')).toBeInTheDocument();

    act(() => {
      ctx.transcriptHandler?.({
        text: 'Final transcript paragraph',
        committedText: 'Final transcript paragraph',
        partialText: '',
        isPartial: false,
        sessionId: 'session-1',
        mode: 'dictation',
      });
      ctx.recordingHandler?.({
        isRecording: false,
        processing: false,
        finished: true,
        sessionId: 'session-1',
        mode: 'dictation',
      });
    });

    expect(screen.getAllByText('Transcript ready').length).toBeGreaterThan(0);
    expect(screen.getByText('Final transcript paragraph')).toBeInTheDocument();
  });

  it('hydrates from cached preload events', () => {
    Object.defineProperty(window, 'openwisprFloating', {
      writable: true,
      value: {
        onRecordingState: vi.fn((handler: RecordingHandler) => {
          handler({
            isRecording: true,
            processing: false,
            finished: false,
            sessionId: 'session-2',
            mode: 'dictation',
          });
          return vi.fn();
        }),
        onTranscription: vi.fn((handler: TranscriptHandler) => {
          handler({
            text: 'Cached transcript text',
            committedText: 'Cached transcript text',
            partialText: '',
            isPartial: false,
            sessionId: 'session-2',
            mode: 'dictation',
          });
          return vi.fn();
        }),
        onAudioVisualizer: vi.fn((handler: AudioHandler) => {
          handler({ levels: new Array(36).fill(0.25), peak: 0.25 });
          return vi.fn();
        }),
        onHotkeyEvent: vi.fn(() => vi.fn()),
        platform: 'win32',
        strings: {
          status: { idle: 'Ready', listening: 'Listening', transcribing: 'Transcribing', processing: 'Finishing', result: 'Transcript ready', error: 'Error' },
          waitingForSpeech: 'Waiting for speech...',
          actions: { cancel: 'Cancel', finish: 'Finish', close: 'Close' },
          resultMeta: {
            transcriptReady: 'Transcript ready',
            livePartialHint: 'Live transcript updates during recording.',
            sessionParagraphHint: 'Live partials stay temporary until stop.',
            genericError: 'Something went wrong.',
          },
        },
      },
    });

    render(<FloatingWindow />);

    expect(screen.getByText('Transcribing')).toBeInTheDocument();
    expect(screen.getByText('Cached transcript text')).toBeInTheDocument();
  });

  it('shows only live partials until stop in session paragraph mode', () => {
    const ctx = installFloatingMock();
    render(<FloatingWindow />);

    act(() => {
      ctx.recordingHandler?.({
        isRecording: true,
        sessionId: 'session-3',
        mode: 'session_paragraph',
      });
      ctx.transcriptHandler?.({
        text: 'Live paragraph preview',
        partialText: 'Live paragraph preview',
        committedText: '',
        isPartial: true,
        sessionId: 'session-3',
        mode: 'session_paragraph',
      });
    });

    expect(screen.getByText('Live paragraph preview')).toBeInTheDocument();

    act(() => {
      ctx.recordingHandler?.({
        isRecording: false,
        processing: true,
        sessionId: 'session-3',
        mode: 'session_paragraph',
      });
      ctx.transcriptHandler?.({
        text: 'One final whole paragraph.',
        committedText: 'One final whole paragraph.',
        partialText: '',
        isPartial: false,
        sessionId: 'session-3',
        mode: 'session_paragraph',
      });
      ctx.recordingHandler?.({
        isRecording: false,
        finished: true,
        sessionId: 'session-3',
        mode: 'session_paragraph',
      });
    });

    expect(screen.getByText('One final whole paragraph.')).toBeInTheDocument();
  });

  it('keeps one timer per session and freezes it at the stop result', () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    vi.spyOn(performance, 'now').mockImplementation(() => now);
    const ctx = installFloatingMock();
    render(<FloatingWindow />);

    act(() => {
      ctx.recordingHandler?.({
        isRecording: true,
        sessionId: 'session-4',
        mode: 'dictation',
      });
    });

    act(() => {
      now = 2500;
      vi.advanceTimersByTime(2500);
    });

    const activeTimerValue = screen.getAllByText(/\d{2}:\d{2}/)[0].textContent;
    expect(activeTimerValue).not.toBe('00:00');

    act(() => {
      ctx.recordingHandler?.({
        isRecording: false,
        processing: true,
        finished: false,
        sessionId: 'session-4',
        mode: 'dictation',
      });
      ctx.recordingHandler?.({
        isRecording: false,
        processing: false,
        finished: true,
        sessionId: 'session-4',
        mode: 'dictation',
      });
      now = 5200;
      vi.advanceTimersByTime(2700);
    });

    expect(screen.getAllByText(/\d{2}:\d{2}/)[0].textContent).toBe(activeTimerValue);

    act(() => {
      ctx.recordingHandler?.({
        isRecording: true,
        sessionId: 'session-7',
        mode: 'dictation',
      });
    });

    expect(screen.getByText('00:00')).toBeInTheDocument();
  });

  it('wires cancel, finish, and close controls', () => {
    const ctx = installFloatingMock();
    render(<FloatingWindow />);

    act(() => {
      ctx.recordingHandler?.({
        isRecording: true,
        sessionId: 'session-5',
        mode: 'dictation',
      });
    });

    fireEvent.click(screen.getByText('Cancel'));
    expect(ctx.cancelRecording).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText('Finish'));
    expect(ctx.finishRecording).toHaveBeenCalledTimes(1);

    act(() => {
      ctx.recordingHandler?.({
        isRecording: false,
        finished: true,
        sessionId: 'session-5',
        mode: 'dictation',
      });
      ctx.transcriptHandler?.({
        text: 'Completed transcript',
        committedText: 'Completed transcript',
        partialText: '',
        isPartial: false,
        sessionId: 'session-5',
        mode: 'dictation',
      });
    });

    fireEvent.click(screen.getByText('Close'));
    expect(ctx.dismissResult).toHaveBeenCalledTimes(1);
  });

  it('tracks transcript scrolling in a real scroll container', () => {
    const ctx = installFloatingMock();
    render(<FloatingWindow />);

    act(() => {
      ctx.recordingHandler?.({
        isRecording: true,
        sessionId: 'session-6',
        mode: 'dictation',
      });
      ctx.transcriptHandler?.({
        text: 'Line one.\nLine two.\nLine three.',
        committedText: 'Line one.\nLine two.\nLine three.',
        partialText: '',
        isPartial: false,
        sessionId: 'session-6',
        mode: 'dictation',
      });
    });

    const container = screen.getByTestId('floating-transcript-scroll');
    expect(container).toHaveStyle({ overflowY: 'auto' });
  });

  it('shows the floating coach result payload when the stop flow emits it', () => {
    const ctx = installFloatingMock();
    render(<FloatingWindow />);

    const payload: HotkeyStopResponse = {
      session_id: 'session-7',
      final_transcription: 'raw final',
      paste_text: 'paste final',
      coach_result: {
        original: 'raw final',
        polished: 'polished final',
        diff: [],
        tips: ['Keep it concise'],
        mistakes: [],
        practice: { prompt: '', answer: '', focus: [] },
        meta: { tone: 'neutral', intent: 'dictation', confidence: 1 },
      },
      coach_status: 'generated',
      duration_ms: 1500,
      segment_count: 2,
    };

    act(() => {
      ctx.coachResultHandler?.(payload);
    });

    expect(screen.getByText('polished final')).toBeInTheDocument();
    expect(screen.getAllByText('Transcript ready').length).toBeGreaterThan(0);

    act(() => {
      ctx.coachResultClearHandler?.();
    });

    expect(screen.getByText('Waiting for speech...')).toBeInTheDocument();
  });
  it('keeps the floating result visible when an idle recording-state arrives after coach-result', () => {
    const ctx = installFloatingMock();
    render(<FloatingWindow />);

    const payload: HotkeyStopResponse = {
      session_id: 'session-8',
      final_transcription: 'faithful final',
      paste_text: 'faithful final',
      coach_result: null,
      coach_status: 'failed',
      coach_error: 'coach_timeout',
      duration_ms: 1200,
      segment_count: 2,
    };

    act(() => {
      ctx.coachResultHandler?.(payload);
    });

    expect(screen.getByText('faithful final')).toBeInTheDocument();
    expect(screen.getAllByText('Transcript ready').length).toBeGreaterThan(0);

    act(() => {
      ctx.recordingHandler?.({
        isRecording: false,
        processing: false,
        finished: false,
        sessionId: null,
        mode: 'dictation',
        error: null,
      });
    });

    expect(screen.getByText('faithful final')).toBeInTheDocument();
    expect(screen.getAllByText('Transcript ready').length).toBeGreaterThan(0);
  });
});

