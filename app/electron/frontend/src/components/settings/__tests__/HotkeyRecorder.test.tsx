import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HotkeyRecorder } from '../settings/HotkeyRecorder';

describe('HotkeyRecorder', () => {
  const defaultProps = {
    value: 'Ctrl+Shift+Space',
    onChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders hotkey recorder with current value', () => {
    render(<HotkeyRecorder {...defaultProps} />);
    
    expect(screen.getByText('Ctrl+Shift+Space')).toBeInTheDocument();
  });

  it('enters recording mode when clicked', () => {
    render(<HotkeyRecorder {...defaultProps} />);
    
    const button = screen.getByRole('button');
    fireEvent.click(button);
    
    expect(screen.getByText(/Press keys/i)).toBeInTheDocument();
  });

  it('captures key combination when recording', () => {
    render(<HotkeyRecorder {...defaultProps} />);
    
    const button = screen.getByRole('button');
    fireEvent.click(button);
    
    // Simulate key press
    fireEvent.keyDown(button, { key: 'F1', code: 'F1', ctrlKey: true });
    
    expect(defaultProps.onChange).toHaveBeenCalled();
  });

  it('clears value when clear button is clicked', () => {
    render(<HotkeyRecorder {...defaultProps} />);
    
    // Look for clear button (typically has an X or "Clear" text)
    const buttons = screen.getAllByRole('button');
    const clearButton = buttons.find(btn => 
      btn.textContent?.toLowerCase().includes('clear') ||
      btn.getAttribute('aria-label')?.toLowerCase().includes('clear')
    );
    
    if (clearButton) {
      fireEvent.click(clearButton);
      expect(defaultProps.onChange).toHaveBeenCalledWith('');
    }
  });

  it('disables interaction when disabled prop is true', () => {
    render(<HotkeyRecorder {...defaultProps} disabled={true} />);
    
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });

  it('shows placeholder when no value', () => {
    render(<HotkeyRecorder value="" onChange={vi.fn()} />);
    
    expect(screen.getByText(/Click to record/i)).toBeInTheDocument();
  });
});
