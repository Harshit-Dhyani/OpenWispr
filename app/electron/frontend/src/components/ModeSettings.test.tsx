import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ModeSettings } from './ModeSettings';
import type { TranscriptionMode } from './ModeSelector';

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  Microphone: () => React.createElement('svg', { 'data-testid': 'microphone-icon' }, 'Microphone'),
  Monitor: () => React.createElement('svg', { 'data-testid': 'monitor-icon' }, 'Monitor'),
  HardDrive: () => React.createElement('svg', { 'data-testid': 'harddrive-icon' }, 'HardDrive'),
  FileText: () => React.createElement('svg', { 'data-testid': 'filetext-icon' }, 'FileText'),
  Languages: () => React.createElement('svg', { 'data-testid': 'languages-icon' }, 'Languages'),
  ToggleRight: () => React.createElement('svg', { 'data-testid': 'toggleright-icon' }, 'ToggleRight'),
  FolderOpen: () => React.createElement('svg', { 'data-testid': 'folderopen-icon' }, 'FolderOpen'),
  Save: () => React.createElement('svg', { 'data-testid': 'save-icon' }, 'Save'),
  AlertCircle: () => React.createElement('svg', { 'data-testid': 'alertcircle-icon' }, 'AlertCircle'),
  Check: () => React.createElement('svg', { 'data-testid': 'check-icon' }, 'Check'),
  Loader2: () => React.createElement('svg', { 'data-testid': 'loader-icon', className: 'animate-spin' }, 'Loader2'),
  Info: () => React.createElement('svg', { 'data-testid': 'info-icon' }, 'Info'),
  Keyboard: () => React.createElement('svg', { 'data-testid': 'keyboard-icon' }, 'Keyboard'),
  Copy: () => React.createElement('svg', { 'data-testid': 'copy-icon' }, 'Copy'),
  Window: () => React.createElement('svg', { 'data-testid': 'window-icon' }, 'Window'),
}));

describe('ModeSettings', () => {
  const defaultHotkeySettings = {
    model_name: 'small' as const,
    key_combination: 'Ctrl+Shift+T',
    auto_inject: true,
    show_floating_window: true,
    language: 'auto',
    copy_to_clipboard: true,
    hold_mode: false,
  };

  const defaultSystemSettings = {
    model_name: 'small' as const,
    audio_source: 'microphone' as const,
    export_format: 'txt' as const,
    auto_segment: true,
    session_save_location: '',
    auto_save_interval: 60,
  };

  const createProps = (mode: TranscriptionMode = 'hotkey') => ({
    mode,
    hotkeySettings: defaultHotkeySettings,
    systemSettings: defaultSystemSettings,
    onHotkeySettingsChange: vi.fn(),
    onSystemSettingsChange: vi.fn(),
    disabled: false,
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Hotkey Mode', () => {
    it('renders hotkey mode panel', () => {
      render(<ModeSettings {...createProps('hotkey')} />);

      expect(screen.getByTestId('mode-settings')).toBeInTheDocument();
      expect(screen.getByTestId('hotkey-mode-panel')).toBeInTheDocument();
    });

    it('displays hotkey mode header', () => {
      render(<ModeSettings {...createProps('hotkey')} />);

      expect(screen.getByText('Hotkey Mode Settings')).toBeInTheDocument();
    });

    it('renders model selection dropdown', () => {
      render(<ModeSettings {...createProps('hotkey')} />);

      expect(screen.getByLabelText(/Transcription Model/i)).toBeInTheDocument();
    });

    it('renders language selection', () => {
      render(<ModeSettings {...createProps('hotkey')} />);

      expect(screen.getByLabelText(/Language/i)).toBeInTheDocument();
    });

    it('renders hotkey configuration input', () => {
      render(<ModeSettings {...createProps('hotkey')} />);

      expect(screen.getByPlaceholderText(/e.g., Ctrl\+Shift\+T/i)).toBeInTheDocument();
    });

    it('calls onHotkeySettingsChange when model changes', async () => {
      const onHotkeySettingsChange = vi.fn();
      render(<ModeSettings {...createProps('hotkey')} onHotkeySettingsChange={onHotkeySettingsChange} />);

      const modelSelect = screen.getByLabelText(/Transcription Model/i);
      await userEvent.selectOptions(modelSelect, 'medium');

      expect(onHotkeySettingsChange).toHaveBeenCalledWith(
        expect.objectContaining({ model_name: 'medium' })
      );
    });

    it('calls onHotkeySettingsChange when language changes', async () => {
      const onHotkeySettingsChange = vi.fn();
      render(<ModeSettings {...createProps('hotkey')} onHotkeySettingsChange={onHotkeySettingsChange} />);

      const languageSelect = screen.getByLabelText(/Language/i);
      await userEvent.selectOptions(languageSelect, 'en');

      expect(onHotkeySettingsChange).toHaveBeenCalledWith(
        expect.objectContaining({ language: 'en' })
      );
    });

    it('calls onHotkeySettingsChange when hotkey changes', async () => {
      const onHotkeySettingsChange = vi.fn();
      render(<ModeSettings {...createProps('hotkey')} onHotkeySettingsChange={onHotkeySettingsChange} />);

      const hotkeyInput = screen.getByPlaceholderText(/e.g., Ctrl\+Shift\+T/i);
      // Use fireEvent.change to set value directly instead of typing character by character
      fireEvent.change(hotkeyInput, { target: { value: 'Ctrl+Shift+R' } });

      expect(onHotkeySettingsChange).toHaveBeenCalledWith(
        expect.objectContaining({ key_combination: 'Ctrl+Shift+R' })
      );
    });

    it('validates hotkey format', async () => {
      render(<ModeSettings {...createProps('hotkey')} />);

      const hotkeyInput = screen.getByPlaceholderText(/e.g., Ctrl\+Shift\+T/i);
      // Use fireEvent.change to set value directly
      fireEvent.change(hotkeyInput, { target: { value: 'T' } });

      // Validation message should appear
      expect(screen.getByText(/Must include a modifier key/i)).toBeInTheDocument();
    });

    it('toggles auto-inject setting', async () => {
      const onHotkeySettingsChange = vi.fn();
      render(<ModeSettings {...createProps('hotkey')} onHotkeySettingsChange={onHotkeySettingsChange} />);

      const toggle = screen.getByRole('switch', { name: /Auto-inject transcription/i });
      await userEvent.click(toggle);

      expect(onHotkeySettingsChange).toHaveBeenCalledWith(
        expect.objectContaining({ auto_inject: false })
      );
    });

    it('toggles floating window setting', async () => {
      const onHotkeySettingsChange = vi.fn();
      render(<ModeSettings {...createProps('hotkey')} onHotkeySettingsChange={onHotkeySettingsChange} />);

      const toggle = screen.getByRole('switch', { name: /Show floating window/i });
      await userEvent.click(toggle);

      expect(onHotkeySettingsChange).toHaveBeenCalledWith(
        expect.objectContaining({ show_floating_window: false })
      );
    });

    it('toggles copy to clipboard setting', async () => {
      const onHotkeySettingsChange = vi.fn();
      render(<ModeSettings {...createProps('hotkey')} onHotkeySettingsChange={onHotkeySettingsChange} />);

      const toggle = screen.getByRole('switch', { name: /Copy to clipboard/i });
      await userEvent.click(toggle);

      expect(onHotkeySettingsChange).toHaveBeenCalledWith(
        expect.objectContaining({ copy_to_clipboard: false })
      );
    });

    it('toggles hold mode setting', async () => {
      const onHotkeySettingsChange = vi.fn();
      render(<ModeSettings {...createProps('hotkey')} onHotkeySettingsChange={onHotkeySettingsChange} />);

      const toggle = screen.getByRole('switch', { name: /Hold mode/i });
      await userEvent.click(toggle);

      expect(onHotkeySettingsChange).toHaveBeenCalledWith(
        expect.objectContaining({ hold_mode: true })
      );
    });
  });

  describe('System Mode', () => {
    it('renders system mode panel', () => {
      render(<ModeSettings {...createProps('system')} />);

      expect(screen.getByTestId('mode-settings')).toBeInTheDocument();
      expect(screen.getByTestId('system-mode-panel')).toBeInTheDocument();
    });

    it('displays system mode header', () => {
      render(<ModeSettings {...createProps('system')} />);

      expect(screen.getByText('System Mode Settings')).toBeInTheDocument();
    });

    it('renders audio source options', () => {
      render(<ModeSettings {...createProps('system')} />);

      // Use getAllByText since these labels may appear in multiple places
      expect(screen.getAllByText('System Audio').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Microphone').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Both').length).toBeGreaterThan(0);
    });

    it('renders export format options', () => {
      render(<ModeSettings {...createProps('system')} />);

      expect(screen.getByText('Plain Text (.txt)')).toBeInTheDocument();
      expect(screen.getByText('JSON (.json)')).toBeInTheDocument();
      expect(screen.getByText('Subtitles (.srt)')).toBeInTheDocument();
      expect(screen.getByText('WebVTT (.vtt)')).toBeInTheDocument();
    });

    it('calls onSystemSettingsChange when audio source changes', async () => {
      const onSystemSettingsChange = vi.fn();
      render(<ModeSettings {...createProps('system')} onSystemSettingsChange={onSystemSettingsChange} />);

      // Get all buttons and find the one with "System Audio" label
      const buttons = screen.getAllByRole('button');
      const systemAudioButton = buttons.find(b => b.textContent?.includes('System Audio'));
      expect(systemAudioButton).toBeDefined();
      if (systemAudioButton) {
        await userEvent.click(systemAudioButton);
        expect(onSystemSettingsChange).toHaveBeenCalledWith(
          expect.objectContaining({ audio_source: 'system' })
        );
      }
    });

    it('calls onSystemSettingsChange when export format changes', async () => {
      const onSystemSettingsChange = vi.fn();
      render(<ModeSettings {...createProps('system')} onSystemSettingsChange={onSystemSettingsChange} />);

      // Get all buttons and find the one with "JSON (.json)" label
      const buttons = screen.getAllByRole('button');
      const jsonButton = buttons.find(b => b.textContent?.includes('JSON'));
      expect(jsonButton).toBeDefined();
      if (jsonButton) {
        await userEvent.click(jsonButton);
        expect(onSystemSettingsChange).toHaveBeenCalledWith(
          expect.objectContaining({ export_format: 'json' })
        );
      }
    });

    it('calls onSystemSettingsChange when session save location changes', async () => {
      const onSystemSettingsChange = vi.fn();
      render(<ModeSettings {...createProps('system')} onSystemSettingsChange={onSystemSettingsChange} />);

      const locationInput = screen.getByPlaceholderText(/Select a folder/i);
      // Use fireEvent.change to set value directly instead of typing character by character
      fireEvent.change(locationInput, { target: { value: '/test/path' } });

      expect(onSystemSettingsChange).toHaveBeenCalledWith(
        expect.objectContaining({ session_save_location: '/test/path' })
      );
    });

    it('toggles auto-segment setting', async () => {
      const onSystemSettingsChange = vi.fn();
      render(<ModeSettings {...createProps('system')} onSystemSettingsChange={onSystemSettingsChange} />);

      const toggle = screen.getByRole('switch', { name: /Auto-segment/i });
      await userEvent.click(toggle);

      expect(onSystemSettingsChange).toHaveBeenCalledWith(
        expect.objectContaining({ auto_segment: false })
      );
    });

    it('opens folder selector when clicking folder button', async () => {
      const mockShowOpenDialog = vi.fn().mockResolvedValue({
        canceled: false,
        filePaths: ['/selected/folder'],
      });

      Object.defineProperty(window, 'electron', {
        value: { showOpenDialog: mockShowOpenDialog },
        writable: true,
      });

      const onSystemSettingsChange = vi.fn();
      render(<ModeSettings {...createProps('system')} onSystemSettingsChange={onSystemSettingsChange} />);

      const folderButton = screen.getByRole('button', { name: /folder/i });
      await userEvent.click(folderButton);

      await waitFor(() => {
        expect(mockShowOpenDialog).toHaveBeenCalledWith({ properties: ['openDirectory'] });
      });
    });
  });

  describe('Loading States', () => {
    it('shows transition animation when mode changes', async () => {
      const { rerender } = render(<ModeSettings {...createProps('hotkey')} />);

      rerender(<ModeSettings {...createProps('system')} />);

      await waitFor(() => {
        expect(screen.getByTestId('system-mode-panel')).toBeInTheDocument();
      });
    });
  });

  describe('Disabled State', () => {
    it('disables all inputs when disabled prop is true', () => {
      render(<ModeSettings {...createProps('hotkey')} disabled />);

      const inputs = screen.getAllByRole('textbox');
      inputs.forEach(input => {
        expect(input).toBeDisabled();
      });
    });

    it('disables toggles when disabled', () => {
      render(<ModeSettings {...createProps('hotkey')} disabled />);

      const toggles = screen.getAllByRole('switch');
      toggles.forEach(toggle => {
        expect(toggle).toBeDisabled();
      });
    });
  });

  describe('Custom ClassName', () => {
    it('applies custom className', () => {
      render(<ModeSettings {...createProps('hotkey')} className="custom-class" />);

      expect(screen.getByTestId('mode-settings')).toHaveClass('custom-class');
    });
  });

  describe('Footer Information', () => {
    it('shows settings save note in footer', () => {
      render(<ModeSettings {...createProps('hotkey')} />);

      expect(screen.getByText(/These settings are saved automatically/)).toBeInTheDocument();
    });
  });
});

describe('ModeSettings Model Options', () => {
  const modelOptions = [
    { value: 'tiny', label: 'Tiny' },
    { value: 'base', label: 'Base' },
    { value: 'small', label: 'Small' },
    { value: 'medium', label: 'Medium' },
    { value: 'large-v3', label: 'Large v3' },
  ];

  it('renders all model options in hotkey mode', () => {
    render(<ModeSettings mode="hotkey" hotkeySettings={{ model_name: 'small' }} />);

    const modelSelect = screen.getByLabelText(/Transcription Model/i);
    modelOptions.forEach(option => {
      expect(modelSelect.querySelector(`option[value="${option.value}"]`)).toBeInTheDocument();
    });
  });

  it('renders all model options in system mode', () => {
    render(<ModeSettings mode="system" systemSettings={{ model_name: 'small' }} />);

    const modelSelect = screen.getByLabelText(/Transcription Model/i);
    modelOptions.forEach(option => {
      expect(modelSelect.querySelector(`option[value="${option.value}"]`)).toBeInTheDocument();
    });
  });
});

describe('ModeSettings Accessibility', () => {
  it('has correct ARIA labels on toggle switches', () => {
    render(<ModeSettings mode="hotkey" hotkeySettings={{}} />);

    const toggles = screen.getAllByRole('switch');
    toggles.forEach(toggle => {
      expect(toggle).toHaveAttribute('aria-checked');
    });
  });

  it('supports keyboard navigation', () => {
    render(<ModeSettings mode="hotkey" hotkeySettings={{}} />);

    const selects = screen.getAllByRole('combobox');
    selects.forEach(select => {
      select.focus();
      expect(document.activeElement).toBe(select);
    });
  });
});
