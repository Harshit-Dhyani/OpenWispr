import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { PartialText } from './PartialText';

describe('PartialText', () => {
  it('renders partial text content', () => {
    render(<PartialText text="Hello world" />);
    
    expect(screen.getByText('Hello world')).toBeInTheDocument();
  });

  it('renders as draft by default', () => {
    render(<PartialText text="Draft text" isDraft={true} />);
    
    const article = screen.getByRole('article');
    expect(article).toHaveAttribute('aria-label', 'Draft transcription');
  });

  it('renders as confirmed when isDraft is false', () => {
    render(<PartialText text="Final text" isDraft={false} />);
    
    const article = screen.getByRole('article');
    expect(article).toHaveAttribute('aria-label', 'Confirmed transcription');
  });

  it('displays confidence percentage', () => {
    render(<PartialText text="Test" confidence={0.85} showConfidence={true} />);
    
    expect(screen.getByText('85% confidence')).toBeInTheDocument();
  });

  it('displays confidence label based on score', () => {
    const { rerender } = render(<PartialText text="Test" confidence={0.9} />);
    expect(screen.getByText('90% confidence')).toHaveClass('text-green-500');

    rerender(<PartialText text="Test" confidence={0.7} />);
    expect(screen.getByText('70% confidence')).toHaveClass('text-yellow-500');

    rerender(<PartialText text="Test" confidence={0.5} />);
    expect(screen.getByText('50% confidence')).toHaveClass('text-orange-500');

    rerender(<PartialText text="Test" confidence={0.3} />);
    expect(screen.getByText('30% confidence')).toHaveClass('text-red-500');
  });

  it('hides confidence when showConfidence is false', () => {
    render(<PartialText text="Test" confidence={0.85} showConfidence={false} />);
    
    expect(screen.queryByText('85% confidence')).not.toBeInTheDocument();
  });

  it('displays timestamp when provided', () => {
    render(<PartialText text="Test" timestamp={65000} />);
    
    expect(screen.getByText('1:05')).toBeInTheDocument();
  });

  it('shows listening indicator for drafts', () => {
    render(<PartialText text="Test" isDraft={true} />);
    
    expect(screen.getByText('Listening...')).toBeInTheDocument();
  });

  it('does not show listening indicator for confirmed', () => {
    render(<PartialText text="Test" isDraft={false} />);
    
    expect(screen.queryByText('Listening...')).not.toBeInTheDocument();
  });

  it('enters edit mode when edit button is clicked', () => {
    const onEdit = vi.fn();
    render(<PartialText text="Original" onEdit={onEdit} />);
    
    const editButton = screen.getByLabelText('Edit text');
    fireEvent.click(editButton);
    
    expect(screen.getByRole('form')).toBeInTheDocument();
    expect(screen.getByLabelText('Edit transcription text')).toHaveValue('Original');
  });

  it('saves edited text when save button is clicked', () => {
    const onEdit = vi.fn();
    render(<PartialText text="Original" onEdit={onEdit} />);
    
    // Enter edit mode
    fireEvent.click(screen.getByLabelText('Edit text'));
    
    // Change text
    const input = screen.getByLabelText('Edit transcription text');
    fireEvent.change(input, { target: { value: 'Modified' } });
    
    // Save
    fireEvent.click(screen.getByLabelText('Save edit'));
    
    expect(onEdit).toHaveBeenCalledWith('Modified');
  });

  it('saves edited text on Enter key', () => {
    const onEdit = vi.fn();
    render(<PartialText text="Original" onEdit={onEdit} />);
    
    // Enter edit mode
    fireEvent.click(screen.getByLabelText('Edit text'));
    
    // Change and press Enter
    const input = screen.getByLabelText('Edit transcription text');
    fireEvent.change(input, { target: { value: 'Modified' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    
    expect(onEdit).toHaveBeenCalledWith('Modified');
  });

  it('cancels edit on Escape key', () => {
    const onEdit = vi.fn();
    render(<PartialText text="Original" onEdit={onEdit} />);
    
    // Enter edit mode
    fireEvent.click(screen.getByLabelText('Edit text'));
    
    // Change and press Escape
    const input = screen.getByLabelText('Edit transcription text');
    fireEvent.change(input, { target: { value: 'Modified' } });
    fireEvent.keyDown(input, { key: 'Escape' });
    
    expect(onEdit).not.toHaveBeenCalled();
    expect(screen.getByText('Original')).toBeInTheDocument();
  });

  it('cancels edit when cancel button is clicked', () => {
    const onEdit = vi.fn();
    render(<PartialText text="Original" onEdit={onEdit} />);
    
    // Enter edit mode
    fireEvent.click(screen.getByLabelText('Edit text'));
    
    // Change and cancel
    const input = screen.getByLabelText('Edit transcription text');
    fireEvent.change(input, { target: { value: 'Modified' } });
    fireEvent.click(screen.getByLabelText('Cancel edit'));
    
    expect(onEdit).not.toHaveBeenCalled();
    expect(screen.getByText('Original')).toBeInTheDocument();
  });

  it('normalizes text when saving edit', () => {
    const onEdit = vi.fn();
    render(<PartialText text="Original" onEdit={onEdit} />);
    
    // Enter edit mode
    fireEvent.click(screen.getByLabelText('Edit text'));
    
    // Save with whitespace that will be trimmed
    const input = screen.getByLabelText('Edit transcription text');
    fireEvent.change(input, { target: { value: 'Modified' } });
    fireEvent.click(screen.getByLabelText('Save edit'));
    
    expect(onEdit).toHaveBeenCalledWith('Modified');
  });

  it('calls onAccept when accept button is clicked', () => {
    const onAccept = vi.fn();
    render(<PartialText text="Test" isDraft={true} onAccept={onAccept} />);
    
    const acceptButton = screen.getByLabelText('Accept as final');
    fireEvent.click(acceptButton);
    
    expect(onAccept).toHaveBeenCalled();
  });

  it('does not show accept button for confirmed text', () => {
    const onAccept = vi.fn();
    render(<PartialText text="Test" isDraft={false} onAccept={onAccept} />);
    
    expect(screen.queryByLabelText('Accept as final')).not.toBeInTheDocument();
  });

  it('calls onDismiss when dismiss button is clicked', () => {
    const onDismiss = vi.fn();
    render(<PartialText text="Test" onDismiss={onDismiss} />);
    
    const dismissButton = screen.getByLabelText('Dismiss');
    fireEvent.click(dismissButton);
    
    expect(onDismiss).toHaveBeenCalled();
  });

  it('does not show edit button when onEdit is not provided', () => {
    render(<PartialText text="Test" />);
    
    expect(screen.queryByLabelText('Edit text')).not.toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<PartialText text="Test" className="custom-class" />);
    
    expect(screen.getByRole('article')).toHaveClass('custom-class');
  });

  it('applies animation classes', () => {
    const { rerender } = render(<PartialText text="Test" animation="pulse" />);
    expect(screen.getByRole('article')).toHaveClass('animate-pulse');

    rerender(<PartialText text="Test" animation="fade" />);
    expect(screen.getByRole('article')).toHaveClass('animate-fade-in');

    rerender(<PartialText text="Test" animation="none" />);
    expect(screen.getByRole('article')).not.toHaveClass('animate-pulse');
  });
});
