import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { FloatingWindow } from '../FloatingWindow';

describe('FloatingWindow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Reset transcriptaFloating mock
    Object.defineProperty(window, 'transcriptaFloating', {
      writable: true,
      value: {
        onRecordingState: vi.fn(() => vi.fn()),
        onTranscription: vi.fn(() => vi.fn()),
        onAudioVisualizer: vi.fn(() => vi.fn()),
      },
    });
  });

  it('renders floating window component', () => {
    render(<FloatingWindow />);
    
    expect(screen.getByText('Ready')).toBeInTheDocument();
    expect(screen.getByText('00:00')).toBeInTheDocument();
    expect(screen.getByText('Waiting for speech...')).toBeInTheDocument();
  });

  it('shows listening state when recording starts', async () => {
    let stateHandler: ((state: { isRecording: boolean; processing?: boolean; finished?: boolean }) => void) | null = null;
    
    Object.defineProperty(window, 'transcriptaFloating', {
      writable: true,
      value: {
        onRecordingState: vi.fn((handler) => {
          stateHandler = handler;
          return vi.fn();
        }),
        onTranscription: vi.fn(() => vi.fn()),
        onAudioVisualizer: vi.fn(() => vi.fn()),
      },
    });

    render(<FloatingWindow />);
    
    // Wait for effect to register handlers
    await waitFor(() => {
      expect(window.transcriptaFloating.onRecordingState).toHaveBeenCalled();
    });

    // Simulate recording start
    if (stateHandler) {
      stateHandler({ isRecording: true });
    }

    await waitFor(() => {
      expect(screen.getByText('Listening...')).toBeInTheDocument();
    });
  });

  it('shows processing state', async () => {
    let stateHandler: ((state: { isRecording: boolean; processing?: boolean; finished?: boolean }) => void) | null = null;
    
    Object.defineProperty(window, 'transcriptaFloating', {
      writable: true,
      value: {
        onRecordingState: vi.fn((handler) => {
          stateHandler = handler;
          return vi.fn();
        }),
        onTranscription: vi.fn(() => vi.fn()),
        onAudioVisualizer: vi.fn(() => vi.fn()),
      },
    });

    render(<FloatingWindow />);
    
    await waitFor(() => {
      expect(window.transcriptaFloating.onRecordingState).toHaveBeenCalled();
    });

    if (stateHandler) {
      stateHandler({ isRecording: false, processing: true });
    }

    await waitFor(() => {
      expect(screen.getByText(/Processing/i)).toBeInTheDocument();
    });
  });

  it('displays transcription text when received', async () => {
    let transcriptionHandler: ((data: { text?: string; isPartial?: boolean } | string) => void) | null = null;
    
    Object.defineProperty(window, 'transcriptaFloating', {
      writable: true,
      value: {
        onRecordingState: vi.fn(() => vi.fn()),
        onTranscription: vi.fn((handler) => {
          transcriptionHandler = handler;
          return vi.fn();
        }),
        onAudioVisualizer: vi.fn(() => vi.fn()),
      },
    });

    render(<FloatingWindow />);
    
    await waitFor(() => {
      expect(window.transcriptaFloating.onTranscription).toHaveBeenCalled();
    });

    if (transcriptionHandler) {
      transcriptionHandler({ text: 'Hello world', isPartial: false });
    }

    await waitFor(() => {
      expect(screen.getByText('Hello world')).toBeInTheDocument();
    });
  });

  it('displays string transcription directly', async () => {
    let transcriptionHandler: ((data: { text?: string; isPartial?: boolean } | string) => void) | null = null;
    
    Object.defineProperty(window, 'transcriptaFloating', {
      writable: true,
      value: {
        onRecordingState: vi.fn(() => vi.fn()),
        onTranscription: vi.fn((handler) => {
          transcriptionHandler = handler;
          return vi.fn();
        }),
        onAudioVisualizer: vi.fn(() => vi.fn()),
      },
    });

    render(<FloatingWindow />);
    
    await waitFor(() => {
      expect(window.transcriptaFloating.onTranscription).toHaveBeenCalled();
    });

    if (transcriptionHandler) {
      transcriptionHandler('Direct text transcription');
    }

    await waitFor(() => {
      expect(screen.getByText('Direct text transcription')).toBeInTheDocument();
    });
  });

  it('renders waveform visualization', () => {
    render(<FloatingWindow />);
    
    // Should render 36 waveform bars
    const bars = document.querySelectorAll('[class*="waveform-bar"]');
    expect(bars.length).toBe(36);
  });

  it('updates timer when recording', async () => {
    vi.useFakeTimers();
    
    let stateHandler: ((state: { isRecording: boolean; processing?: boolean; finished?: boolean }) => void) | null = null;
    
    Object.defineProperty(window, 'transcriptaFloating', {
      writable: true,
      value: {
        onRecordingState: vi.fn((handler) => {
          stateHandler = handler;
          return vi.fn();
        }),
        onTranscription: vi.fn(() => vi.fn()),
        onAudioVisualizer: vi.fn(() => vi.fn()),
      },
    });

    render(<FloatingWindow />);
    
    await waitFor(() => {
      expect(window.transcriptaFloating.onRecordingState).toHaveBeenCalled();
    });

    if (stateHandler) {
      stateHandler({ isRecording: true });
    }

    // Advance timer by 5 seconds
    vi.advanceTimersByTime(5000);

    await waitFor(() => {
      expect(screen.getByText('00:05')).toBeInTheDocument();
    });

    vi.useRealTimers();
  });
});
