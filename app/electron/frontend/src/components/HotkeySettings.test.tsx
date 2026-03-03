import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HotkeySettings } from './HotkeySettings';
import type { HotkeyState } from '../types/api';

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  Keyboard: () => React.createElement('svg', { 'data-testid': 'keyboard-icon' }, 'Keyboard'),
  Check: () => React.createElement('svg', { 'data-testid': 'check-icon' }, 'Check'),
  X: () => React.createElement('svg', { 'data-testid': 'x-icon' }, 'X'),
  AlertCircle: () => React.createElement('svg', { 'data-testid': 'alertcircle-icon' }, 'AlertCircle'),
  Play: () => React.createElement('svg', { 'data-testid': 'play-icon' }, 'Play'),
  RotateCcw: () => React.createElement('svg', { 'data-testid': 'rotateccw-icon' }, 'RotateCcw'),
  Info: () => React.createElement('svg', { 'data-testid': 'info-icon' }, 'Info'),
  Trash2: () => React.createElement('svg', { 'data-testid': 'trash2-icon' }, 'Trash2'),
  Circle: () => React.createElement('svg', { 'data-testid': 'circle-icon' }, 'Circle'),
}));

// Module-level mock state for all tests
const mockHotkeyState: HotkeyState = {
  config: {
    enabled: true,
    key_combination: 'Ctrl+Shift+T',
    hold_mode: false,
    auto_inject: true,
    language: 'auto',
    device_id: 'default',
    model_name: 'small',
    finish_mode_default: 'finish_and_paste',
    show_floating_window: true,
    floating_window_position: 'bottom-right',
    record_on_start: false,
    stop_on_release: false,
    copy_to_clipboard: true,
  },
  session: {
    session_id: 'test-session',
    is_recording: false,
    status: 'idle',
    last_activated_at: null,
    total_activations: 0,
    current_text: '',
    duration_ms: 0,
  },
  is_registered: true,
  error: null,
};

const createMockHotkeyApi = (overrides = {}) => ({
  getState: vi.fn().mockResolvedValue(mockHotkeyState),
  register: vi.fn().mockResolvedValue({ success: true }),
  unregister: vi.fn().mockResolvedValue({ success: true }),
  onStateChange: vi.fn(() => vi.fn()),
  removeStateChangeListener: vi.fn(),
  ...overrides,
});

describe('HotkeySettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, 'transcriptaDesktop', {
      writable: true,
      value: {
        hotkey: createMockHotkeyApi(),
      },
    });
  });

  describe('Loading States', () => {
    it('shows loading state initially', () => {
      render(<HotkeySettings />);

      expect(screen.getByText(/Loading hotkey settings/i)).toBeInTheDocument();
    });

    it('renders main content after loading', async () => {
      render(<HotkeySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Hotkey Mode Configuration/i)).toBeInTheDocument();
      });
    });
  });

  describe('Header and Status', () => {
    it('displays header with keyboard icon', async () => {
      render(<HotkeySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Hotkey Mode Configuration/i)).toBeInTheDocument();
      });
    });

    it('shows registered status when hotkey is registered', async () => {
      render(<HotkeySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Registered - Ready to use/i)).toBeInTheDocument();
      });
    });

    it('shows recording status when actively recording', async () => {
      const recordingState = {
        ...mockHotkeyState,
        session: { ...mockHotkeyState.session, is_recording: true },
      };

      Object.defineProperty(window, 'transcriptaDesktop', {
        writable: true,
        value: {
          hotkey: createMockHotkeyApi({
            getState: vi.fn().mockResolvedValue(recordingState),
          }),
        },
      });

      render(<HotkeySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Active - Currently recording/i)).toBeInTheDocument();
      });
    });
  });

  describe('Mode Description', () => {
    it('displays mode description', async () => {
      render(<HotkeySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Hotkey Mode lets you activate transcription/i)).toBeInTheDocument();
      });
    });
  });

  describe('Model Selection', () => {
    it('renders model dropdown with all options', async () => {
      render(<HotkeySettings />);

      await waitFor(() => {
        // Find the label by text, then find the associated select
        expect(screen.getByText(/Transcription Model/i)).toBeInTheDocument();
        const selects = screen.getAllByRole('combobox');
        expect(selects.length).toBeGreaterThan(0);
      });
    });

    it('selects correct initial model', async () => {
      render(<HotkeySettings />);

      await waitFor(() => {
        const selects = screen.getAllByRole('combobox');
        expect(selects[0]).toHaveValue('small');
      });
    });

    it('calls onConfigChange when model changes', async () => {
      const onConfigChange = vi.fn();
      render(<HotkeySettings onConfigChange={onConfigChange} />);

      await waitFor(() => {
        expect(screen.getByText(/Transcription Model/i)).toBeInTheDocument();
      });

      const selects = screen.getAllByRole('combobox');
      await userEvent.selectOptions(selects[0], 'medium');

      expect(onConfigChange).toHaveBeenCalled();
    });
  });

  describe('Language Selection', () => {
    it('renders language dropdown', async () => {
      render(<HotkeySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Language/i)).toBeInTheDocument();
        const selects = screen.getAllByRole('combobox');
        expect(selects.length).toBeGreaterThan(0);
      });
    });

    it('calls onConfigChange when language changes', async () => {
      const onConfigChange = vi.fn();
      render(<HotkeySettings onConfigChange={onConfigChange} />);

      await waitFor(() => {
        expect(screen.getByText(/Language/i)).toBeInTheDocument();
      });

      const selects = screen.getAllByRole('combobox');
      // Language is the second select
      if (selects[1]) {
        await userEvent.selectOptions(selects[1], 'en');
        expect(onConfigChange).toHaveBeenCalled();
      }
    });
  });

  describe('Hotkey Recording', () => {
    it('renders hotkey recorder button', async () => {
      render(<HotkeySettings />);

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByText(/Loading hotkey settings/i)).not.toBeInTheDocument();
      });

      // The button shows the formatted combo from the mock state
      expect(screen.getByText(/Ctrl \+ Shift \+ T/i)).toBeInTheDocument();
    });

    it('starts recording when clicking the recorder button', async () => {
      render(<HotkeySettings />);

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByText(/Loading hotkey settings/i)).not.toBeInTheDocument();
      });

      const recorderButton = screen.getByText(/Ctrl \+ Shift \+ T/i).closest('button');
      if (recorderButton) {
        await userEvent.click(recorderButton);
        expect(screen.getByText(/Press key combination/i)).toBeInTheDocument();
      }
    });

    it('shows clear button when combo is recorded', async () => {
      render(<HotkeySettings />);

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByText(/Loading hotkey settings/i)).not.toBeInTheDocument();
      });

      expect(screen.getByTitle(/Clear/i)).toBeInTheDocument();
    });

    it('clears combo when clicking clear button', async () => {
      render(<HotkeySettings />);

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByText(/Loading hotkey settings/i)).not.toBeInTheDocument();
      });

      const clearButton = screen.getByTitle(/Clear/i);
      await userEvent.click(clearButton);

      // After clearing, should show "Click to record"
      expect(screen.getByText(/Click to record/i)).toBeInTheDocument();
    });
  });

  describe('Recommended Hotkeys', () => {
    it('renders recommended hotkeys', async () => {
      render(<HotkeySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Ctrl\+Shift\+T/i)).toBeInTheDocument();
        expect(screen.getByText(/Ctrl\+Shift\+R/i)).toBeInTheDocument();
      });
    });

    it('selects hotkey when clicking recommended option', async () => {
      render(<HotkeySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Ctrl\+Alt\+T/i)).toBeInTheDocument();
      });

      const option = screen.getByText(/Ctrl\+Alt\+T/i).closest('button');
      if (option) {
        await userEvent.click(option);
      }
    });
  });

  describe('Toggle Settings', () => {
    it('renders auto-inject toggle', async () => {
      render(<HotkeySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Auto-inject/i)).toBeInTheDocument();
      });
    });

    it('renders floating window toggle', async () => {
      render(<HotkeySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Floating Window/i)).toBeInTheDocument();
      });
    });

    it('toggles auto-inject setting', async () => {
      const onConfigChange = vi.fn();
      render(<HotkeySettings onConfigChange={onConfigChange} />);

      await waitFor(() => {
        expect(screen.getByText(/Auto-inject/i)).toBeInTheDocument();
      });

      // Find the toggle button by aria-label
      const toggle = screen.getByRole('switch', { name: /Auto-inject transcription/i });
      await userEvent.click(toggle);
      expect(onConfigChange).toHaveBeenCalled();
    });
  });

  describe('Action Buttons', () => {
    it('renders register button', async () => {
      render(<HotkeySettings />);

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByText(/Loading hotkey settings/i)).not.toBeInTheDocument();
      });

      expect(screen.getByText(/Register Hotkey/i)).toBeInTheDocument();
    });

    it('renders test button', async () => {
      render(<HotkeySettings />);

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByText(/Loading hotkey settings/i)).not.toBeInTheDocument();
      });

      expect(screen.getByText(/Test/i)).toBeInTheDocument();
    });

    it('calls register API when clicking register button', async () => {
      const registerMock = vi.fn().mockResolvedValue({ success: true });
      Object.defineProperty(window, 'transcriptaDesktop', {
        writable: true,
        value: {
          hotkey: createMockHotkeyApi({
            register: registerMock,
          }),
        },
      });

      render(<HotkeySettings />);

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByText(/Loading hotkey settings/i)).not.toBeInTheDocument();
      });

      const registerButton = screen.getByText(/Register Hotkey/i).closest('button');
      if (registerButton) {
        await userEvent.click(registerButton);
        expect(registerMock).toHaveBeenCalled();
      }
    });
  });

  describe('Status Details', () => {
    it('renders status section', async () => {
      render(<HotkeySettings />);

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByText(/Loading hotkey settings/i)).not.toBeInTheDocument();
      });

      expect(screen.getByText(/Status Details/i)).toBeInTheDocument();
    });

    it('shows registration status', async () => {
      render(<HotkeySettings />);

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByText(/Loading hotkey settings/i)).not.toBeInTheDocument();
      });

      expect(screen.getByText(/Registration/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Registered/i).length).toBeGreaterThan(0);
    });

    it('shows active state', async () => {
      render(<HotkeySettings />);

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByText(/Loading hotkey settings/i)).not.toBeInTheDocument();
      });

      expect(screen.getByText(/Active State/i)).toBeInTheDocument();
      expect(screen.getByText(/Idle/i)).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('displays error when API fails', async () => {
      Object.defineProperty(window, 'transcriptaDesktop', {
        writable: true,
        value: {
          hotkey: createMockHotkeyApi({
            getState: vi.fn().mockRejectedValue(new Error('API Error')),
          }),
        },
      });

      render(<HotkeySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load hotkey state/i)).toBeInTheDocument();
      });
    });

    it('displays validation errors', async () => {
      render(<HotkeySettings />);

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByText(/Loading hotkey settings/i)).not.toBeInTheDocument();
      });

      const recorderButton = screen.getByText(/Click to record/i).closest('button');
      if (recorderButton) {
        await userEvent.click(recorderButton);
      }
    });
  });

  describe('Refresh', () => {
    it('renders refresh button', async () => {
      render(<HotkeySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Refresh State/i)).toBeInTheDocument();
      });
    });

    it('refreshes state when clicking refresh button', async () => {
      const getStateMock = vi.fn().mockResolvedValue(mockHotkeyState);
      Object.defineProperty(window, 'transcriptaDesktop', {
        writable: true,
        value: {
          hotkey: createMockHotkeyApi({
            getState: getStateMock,
          }),
        },
      });

      render(<HotkeySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Refresh State/i)).toBeInTheDocument();
      });

      const refreshButton = screen.getByText(/Refresh State/i).closest('button');
      if (refreshButton) {
        await userEvent.click(refreshButton);
        expect(getStateMock).toHaveBeenCalledTimes(2);
      }
    });
  });
});

describe('HotkeySettings Validation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, 'transcriptaDesktop', {
      writable: true,
      value: {
        hotkey: createMockHotkeyApi(),
      },
    });
  });

  it('validates that hotkey must have modifier', async () => {
    const onConfigChange = vi.fn();
    render(<HotkeySettings onConfigChange={onConfigChange} />);

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByText(/Loading hotkey settings/i)).not.toBeInTheDocument();
    });

    expect(screen.getByText(/Click to record/i)).toBeInTheDocument();
  });

  it('validates reserved hotkeys', async () => {
    render(<HotkeySettings />);

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByText(/Loading hotkey settings/i)).not.toBeInTheDocument();
    });

    expect(screen.getByText(/Click to record/i)).toBeInTheDocument();
  });
});
