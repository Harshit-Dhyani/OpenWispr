import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ActivityFeed } from '../ActivityFeed';

describe('ActivityFeed layout regressions', () => {
  it('keeps session pulse empty state text wrapped instead of truncated', () => {
    render(<ActivityFeed session={null} transcript={[]} variant="sidebar" />);

    const heading = screen.getByRole('heading', { name: 'No Session' });
    const message = screen.getByText('Start a session to stream transcript, review flags, and notes.');

    expect(heading.className).toContain('break-words');
    expect(heading.className).not.toContain('truncate');

    expect(message.className).toContain('break-words');
    expect(message.className).not.toContain('truncate');
  });
});
