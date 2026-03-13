import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  ModeSelector,
  ModeSelectorCompact,
  ModeToggle,
  type TranscriptionMode,
} from './ModeSelector';

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  Microphone: () => React.createElement('svg', { 'data-testid': 'microphone-icon' }, 'Microphone'),
  Monitor: () => React.createElement('svg', { 'data-testid': 'monitor-icon' }, 'Monitor'),
  Check: () => React.createElement('svg', { 'data-testid': 'check-icon' }, 'Check'),
  Info: () => React.createElement('svg', { 'data-testid': 'info-icon' }, 'Info'),
  Loader2: () => React.createElement('svg', { 'data-testid': 'loader-icon', className: 'animate-spin' }, 'Loader'),
}));

describe('ModeSelector', () => {
  const defaultProps = {
    currentMode: 'hotkey' as TranscriptionMode,
    onModeChange: vi.fn(),
    disabled: false,
    loading: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders mode options correctly', () => {
    render(<ModeSelector {...defaultProps} />);

    expect(screen.getByTestId('mode-selector')).toBeInTheDocument();
    expect(screen.getByTestId('mode-option-hotkey')).toBeInTheDocument();
    expect(screen.getByTestId('mode-option-system')).toBeInTheDocument();
  });

  it('displays hotkey mode as selected when currentMode is hotkey', () => {
    render(<ModeSelector {...defaultProps} currentMode="hotkey" />);

    const hotkeyOption = screen.getByTestId('mode-option-hotkey');
    expect(hotkeyOption).toHaveAttribute('aria-pressed', 'true');

    const systemOption = screen.getByTestId('mode-option-system');
    expect(systemOption).toHaveAttribute('aria-pressed', 'false');
  });

  it('displays system mode as selected when currentMode is system', () => {
    render(<ModeSelector {...defaultProps} currentMode="system" />);

    const systemOption = screen.getByTestId('mode-option-system');
    expect(systemOption).toHaveAttribute('aria-pressed', 'true');

    const hotkeyOption = screen.getByTestId('mode-option-hotkey');
    expect(hotkeyOption).toHaveAttribute('aria-pressed', 'false');
  });

  it('calls onModeChange when clicking unselected mode', async () => {
    const onModeChange = vi.fn();
    render(<ModeSelector {...defaultProps} currentMode="hotkey" onModeChange={onModeChange} />);

    const systemOption = screen.getByTestId('mode-option-system');
    await userEvent.click(systemOption);

    expect(onModeChange).toHaveBeenCalledWith('system');
  });

  it('does not call onModeChange when clicking already selected mode', async () => {
    const onModeChange = vi.fn();
    render(<ModeSelector {...defaultProps} currentMode="hotkey" onModeChange={onModeChange} />);

    const hotkeyOption = screen.getByTestId('mode-option-hotkey');
    await userEvent.click(hotkeyOption);

    expect(onModeChange).not.toHaveBeenCalled();
  });

  it('disables interaction when disabled prop is true', () => {
    render(<ModeSelector {...defaultProps} disabled />);

    const systemOption = screen.getByTestId('mode-option-system');
    expect(systemOption).toBeDisabled();
  });

  it('shows loading spinner when loading prop is true', () => {
    render(<ModeSelector {...defaultProps} loading />);

    expect(screen.getByTestId('mode-selector')).toBeInTheDocument();
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('displays mode labels correctly', () => {
    render(<ModeSelector {...defaultProps} />);

    // Use getAllByText since 'Hotkey Mode' and 'System Mode' appear in multiple places
    const hotkeyLabels = screen.getAllByText('Hotkey Mode');
    const systemLabels = screen.getAllByText('System Mode');

    expect(hotkeyLabels.length).toBeGreaterThan(0);
    expect(systemLabels.length).toBeGreaterThan(0);
  });

  it('displays mode descriptions', () => {
    render(<ModeSelector {...defaultProps} />);

    expect(screen.getByText(/Activate transcription with a keyboard shortcut/)).toBeInTheDocument();
    expect(screen.getByText(/Continuous recording with session management/)).toBeInTheDocument();
  });

  it('displays feature lists for each mode', () => {
    render(<ModeSelector {...defaultProps} />);

    expect(screen.getByText('Keyboard shortcut activation')).toBeInTheDocument();
    expect(screen.getByText('Continuous recording')).toBeInTheDocument();
  });

  it('shows active badge for selected mode', () => {
    render(<ModeSelector {...defaultProps} currentMode="hotkey" />);

    const hotkeyOption = screen.getByTestId('mode-option-hotkey');
    expect(hotkeyOption.textContent).toContain('Active');
  });

  it('applies custom className', () => {
    render(<ModeSelector {...defaultProps} className="custom-class" />);

    expect(screen.getByTestId('mode-selector')).toHaveClass('custom-class');
  });

  it('shows mode comparison hint', () => {
    render(<ModeSelector {...defaultProps} />);

    // Check that the hint section contains the expected text parts
    const hintContainer = screen.getByText('Select your preferred mode').closest('div')?.parentElement;
    expect(hintContainer).toBeInTheDocument();
  });
});

describe('ModeSelectorCompact', () => {
  const defaultProps = {
    currentMode: 'hotkey' as TranscriptionMode,
    onModeChange: vi.fn(),
    disabled: false,
    loading: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders compact mode buttons', () => {
    render(<ModeSelectorCompact {...defaultProps} />);

    expect(screen.getByTestId('mode-selector-compact')).toBeInTheDocument();
    expect(screen.getByTestId('mode-option-compact-hotkey')).toBeInTheDocument();
    expect(screen.getByTestId('mode-option-compact-system')).toBeInTheDocument();
  });

  it('indicates selected mode with checkmark', () => {
    render(<ModeSelectorCompact {...defaultProps} currentMode="hotkey" />);

    const hotkeyButton = screen.getByTestId('mode-option-compact-hotkey');
    expect(hotkeyButton.querySelector('svg')).toBeInTheDocument();
  });

  it('calls onModeChange when clicking different mode', async () => {
    const onModeChange = vi.fn();
    render(<ModeSelectorCompact {...defaultProps} onModeChange={onModeChange} />);

    const systemButton = screen.getByTestId('mode-option-compact-system');
    await userEvent.click(systemButton);

    expect(onModeChange).toHaveBeenCalledWith('system');
  });

  it('shows spinner when loading', () => {
    render(<ModeSelectorCompact {...defaultProps} loading currentMode="hotkey" />);

    const hotkeyButton = screen.getByTestId('mode-option-compact-hotkey');
    expect(hotkeyButton.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('disables buttons when disabled', () => {
    render(<ModeSelectorCompact {...defaultProps} disabled />);

    expect(screen.getByTestId('mode-option-compact-hotkey')).toBeDisabled();
    expect(screen.getByTestId('mode-option-compact-system')).toBeDisabled();
  });
});

describe('ModeToggle', () => {
  const defaultProps = {
    currentMode: 'hotkey' as TranscriptionMode,
    onModeChange: vi.fn(),
    disabled: false,
    loading: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders toggle switch', () => {
    render(<ModeToggle {...defaultProps} />);

    expect(screen.getByTestId('mode-toggle')).toBeInTheDocument();
    expect(screen.getByTestId('mode-toggle-button')).toBeInTheDocument();
  });

  it('shows Hotkey label when mode is hotkey', () => {
    render(<ModeToggle {...defaultProps} currentMode="hotkey" />);

    const hotkeyLabel = screen.getByText('Hotkey');
    expect(hotkeyLabel).toHaveClass('text-lawn-border');

    const systemLabel = screen.getByText('System');
    expect(systemLabel).toHaveClass('text-stone-400');
  });

  it('shows System label when mode is system', () => {
    render(<ModeToggle {...defaultProps} currentMode="system" />);

    const systemLabel = screen.getByText('System');
    expect(systemLabel).toHaveClass('text-lawn-border');

    const hotkeyLabel = screen.getByText('Hotkey');
    expect(hotkeyLabel).toHaveClass('text-stone-400');
  });

  it('toggles mode when clicking switch', async () => {
    const onModeChange = vi.fn();
    render(<ModeToggle {...defaultProps} currentMode="hotkey" onModeChange={onModeChange} />);

    const toggle = screen.getByTestId('mode-toggle-button');
    await userEvent.click(toggle);

    expect(onModeChange).toHaveBeenCalledWith('system');
  });

  it('toggles from system to hotkey', async () => {
    const onModeChange = vi.fn();
    render(<ModeToggle {...defaultProps} currentMode="system" onModeChange={onModeChange} />);

    const toggle = screen.getByTestId('mode-toggle-button');
    await userEvent.click(toggle);

    expect(onModeChange).toHaveBeenCalledWith('hotkey');
  });

  it('disables toggle when disabled prop is true', () => {
    render(<ModeToggle {...defaultProps} disabled />);

    expect(screen.getByTestId('mode-toggle-button')).toBeDisabled();
  });

  it('shows loading spinner when loading', () => {
    render(<ModeToggle {...defaultProps} loading />);

    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });

  it('has correct aria-label', () => {
    render(<ModeToggle {...defaultProps} currentMode="hotkey" />);

    const toggle = screen.getByTestId('mode-toggle-button');
    expect(toggle).toHaveAttribute('aria-label', 'Switch to System mode');
  });

  it('updates aria-label based on current mode', () => {
    render(<ModeToggle {...defaultProps} currentMode="system" />);

    const toggle = screen.getByTestId('mode-toggle-button');
    expect(toggle).toHaveAttribute('aria-label', 'Switch to Hotkey mode');
  });
});

describe('ModeSelector Accessibility', () => {
  it('has correct ARIA attributes on mode options', () => {
    render(<ModeSelector currentMode="hotkey" onModeChange={vi.fn()} />);

    const hotkeyOption = screen.getByTestId('mode-option-hotkey');
    // Button element has implicit role of "button"
    expect(hotkeyOption.tagName.toLowerCase()).toBe('button');
    expect(hotkeyOption).toHaveAttribute('aria-pressed', 'true');
    expect(hotkeyOption).toHaveAttribute('aria-label', 'Select Hotkey Mode');
  });

  it('supports keyboard navigation', () => {
    render(<ModeSelector currentMode="hotkey" onModeChange={vi.fn()} />);

    const hotkeyOption = screen.getByTestId('mode-option-hotkey');
    hotkeyOption.focus();
    expect(document.activeElement).toBe(hotkeyOption);
  });
});

describe('ModeSelector Responsive Design', () => {
  it('renders grid layout', () => {
    render(<ModeSelector currentMode="hotkey" onModeChange={vi.fn()} />);

    const grid = screen.getByTestId('mode-selector').querySelector('.grid');
    expect(grid).toHaveClass('grid-cols-1', 'sm:grid-cols-2');
  });
});
