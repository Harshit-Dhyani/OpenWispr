import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ActivityFeed } from '../ActivityFeed';
import { createMockSessionSummary, createMockSegment, createMockFormula, createMockHealth } from '../../test/factories';

describe('ActivityFeed', () => {
  const defaultProps = {
    session: createMockSessionSummary(),
    transcript: [createMockSegment()],
    health: createMockHealth(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders activity feed with session info', () => {
    render(<ActivityFeed {...defaultProps} />);
    
    expect(screen.getByText('Activity Feed')).toBeInTheDocument();
    expect(screen.getByText('Test Session')).toBeInTheDocument();
  });

  it('displays transcript segments', () => {
    const segments = [
      createMockSegment({ id: '1', text: 'First segment', display_text: 'First segment' }),
      createMockSegment({ id: '2', text: 'Second segment', display_text: 'Second segment' }),
    ];
    
    render(<ActivityFeed {...defaultProps} transcript={segments} />);
    
    expect(screen.getByText('First segment')).toBeInTheDocument();
    expect(screen.getByText('Second segment')).toBeInTheDocument();
  });

  it('displays session status badge', () => {
    render(<ActivityFeed {...defaultProps} session={createMockSessionSummary({ status: 'running' })} />);
    
    expect(screen.getByText('running')).toBeInTheDocument();
  });

  it('displays health metrics', () => {
    render(<ActivityFeed {...defaultProps} />);
    
    expect(screen.getByText(/GPU/i)).toBeInTheDocument();
    expect(screen.getByText(/Queue/i)).toBeInTheDocument();
  });

  it('displays empty state when no session', () => {
    render(<ActivityFeed {...defaultProps} session={null} />);
    
    expect(screen.getByText(/No active session/i)).toBeInTheDocument();
  });

  it('displays formula count', () => {
    render(<ActivityFeed {...defaultProps} session={createMockSessionSummary({ formula_count: 5 })} />);
    
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('displays segment count', () => {
    render(<ActivityFeed {...defaultProps} session={createMockSessionSummary({ segment_count: 10 })} />);
    
    expect(screen.getByText('10')).toBeInTheDocument();
  });

  it('shows error state in health', () => {
    render(<ActivityFeed {...defaultProps} health={createMockHealth({ last_error: 'Test error' })} />);
    
    expect(screen.getByText('Test error')).toBeInTheDocument();
  });

  it('displays backpressure warnings', () => {
    render(<ActivityFeed {...defaultProps} health={createMockHealth({ stt_backpressure_state: 'elevated' })} />);
    
    expect(screen.getByText(/elevated/i)).toBeInTheDocument();
  });
});
