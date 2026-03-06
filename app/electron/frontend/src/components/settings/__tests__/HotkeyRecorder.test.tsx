import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  formatHotkeyCombo,
  HotkeyRecorder,
  normalizeAcceleratorFromKeyboardEvent,
} from '../HotkeyRecorder';

describe('HotkeyRecorder', () => {
  const defaultProps = {
    value: 'CommandOrControl+Shift+Space',
    onChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders normalized hotkeys with friendly labels', () => {
    render(<HotkeyRecorder {...defaultProps} />);

    expect(screen.getByText('Ctrl+Shift+Space')).toBeInTheDocument();
  });

  it('shows None when no hotkey is configured', () => {
    render(<HotkeyRecorder value="" onChange={vi.fn()} />);

    expect(screen.getByText('None')).toBeInTheDocument();
  });

  it('enters recording mode when clicked', () => {
    render(<HotkeyRecorder {...defaultProps} />);

    fireEvent.click(screen.getByRole('button'));

    expect(screen.getByText(/Press key combination/i)).toBeInTheDocument();
  });

  it('captures Electron-compatible accelerators for modifier combos', () => {
    render(<HotkeyRecorder {...defaultProps} />);

    fireEvent.click(screen.getByRole('button'));
    fireEvent.keyDown(window, { key: 't', ctrlKey: true, shiftKey: true });

    expect(defaultProps.onChange).toHaveBeenCalledWith('CommandOrControl+Shift+T');
  });

  it('captures function keys without modifiers', () => {
    render(<HotkeyRecorder {...defaultProps} />);

    fireEvent.click(screen.getByRole('button'));
    fireEvent.keyDown(window, { key: 'F9' });

    expect(defaultProps.onChange).toHaveBeenCalledWith('F9');
  });

  it('disables interaction when disabled prop is true', () => {
    render(<HotkeyRecorder {...defaultProps} disabled />);

    expect(screen.getByRole('button')).toBeDisabled();
  });
});

describe('normalizeAcceleratorFromKeyboardEvent', () => {
  it('normalizes browser modifier names to Electron accelerators', () => {
    const event = new KeyboardEvent('keydown', {
      key: 'y',
      ctrlKey: true,
      altKey: true,
    });

    expect(normalizeAcceleratorFromKeyboardEvent(event)).toBe('CommandOrControl+Alt+Y');
  });

  it('treats space as a valid accelerator key', () => {
    const event = new KeyboardEvent('keydown', {
      key: ' ',
      ctrlKey: true,
      shiftKey: true,
    });

    expect(normalizeAcceleratorFromKeyboardEvent(event)).toBe('CommandOrControl+Shift+Space');
  });

  it('ignores modifier-only key presses', () => {
    const event = new KeyboardEvent('keydown', {
      key: 'Control',
      ctrlKey: true,
    });

    expect(normalizeAcceleratorFromKeyboardEvent(event)).toBeNull();
  });
});

describe('formatHotkeyCombo', () => {
  it('formats stored accelerators for display', () => {
    expect(formatHotkeyCombo('CommandOrControl+Super+T')).toBe('Ctrl+Win+T');
  });
});
