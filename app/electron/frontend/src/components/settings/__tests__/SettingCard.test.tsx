import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SettingCard } from '../SettingCard';

describe('SettingCard', () => {
  const defaultProps = {
    title: 'Test Setting',
    description: 'This is a test setting description',
    children: <input type="text" placeholder="Enter value" />,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders setting card with title and description', () => {
    render(<SettingCard {...defaultProps} />);
    
    expect(screen.getByText('Test Setting')).toBeInTheDocument();
    expect(screen.getByText('This is a test setting description')).toBeInTheDocument();
  });

  it('renders children content', () => {
    render(<SettingCard {...defaultProps} />);
    
    expect(screen.getByPlaceholderText('Enter value')).toBeInTheDocument();
  });

  it('shows changed indicator when changed prop is true', () => {
    render(<SettingCard {...defaultProps} changed={true} />);
    
    // Changed indicator is typically a visual element
    const changedIndicator = document.querySelector('[data-testid="changed-indicator"], .changed, [class*="changed"]');
    expect(changedIndicator).toBeInTheDocument();
  });

  it('calls onReset when reset button is clicked', () => {
    const onReset = vi.fn();
    render(<SettingCard {...defaultProps} changed={true} onReset={onReset} />);
    
    const resetButton = screen.getByRole('button', { name: /reset/i }) || 
                       screen.getByTitle(/reset/i) ||
                       document.querySelector('[data-testid="reset-button"]');
    
    if (resetButton) {
      fireEvent.click(resetButton);
      expect(onReset).toHaveBeenCalled();
    }
  });

  it('displays error message when error prop is provided', () => {
    render(<SettingCard {...defaultProps} error="Invalid value" />);
    
    expect(screen.getByText('Invalid value')).toBeInTheDocument();
  });

  it('applies disabled state', () => {
    render(<SettingCard {...defaultProps} disabled={true} />);
    
    const card = document.querySelector('[class*="disabled"], [disabled]');
    expect(card).toBeInTheDocument();
  });
});
