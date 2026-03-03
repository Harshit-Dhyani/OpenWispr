import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { AudioVisualizer } from './AudioVisualizer';

// Mock canvas context
const mockFillRect = vi.fn();
const mockClearRect = vi.fn();
const mockBeginPath = vi.fn();
const mockArc = vi.fn();
const mockStroke = vi.fn();
const mockFill = vi.fn();
const mockRoundRect = vi.fn();
const mockMoveTo = vi.fn();
const mockLineTo = vi.fn();
const mockCreateLinearGradient = vi.fn(() => ({
  addColorStop: vi.fn(),
}));
const mockCreateRadialGradient = vi.fn(() => ({
  addColorStop: vi.fn(),
}));
const mockScale = vi.fn();

const mockContext = {
  fillRect: mockFillRect,
  clearRect: mockClearRect,
  beginPath: mockBeginPath,
  arc: mockArc,
  stroke: mockStroke,
  fill: mockFill,
  roundRect: mockRoundRect,
  moveTo: mockMoveTo,
  lineTo: mockLineTo,
  createLinearGradient: mockCreateLinearGradient,
  createRadialGradient: mockCreateRadialGradient,
  scale: mockScale,
};

// Mock getContext
HTMLCanvasElement.prototype.getContext = vi.fn(() => mockContext) as unknown as typeof HTMLCanvasElement.prototype.getContext;

// Track animation frame callbacks for cleanup
let rafId = 0;
const rafCallbacks = new Map<number, ReturnType<typeof setTimeout>>();

// Mock requestAnimationFrame with cleanup tracking
global.requestAnimationFrame = vi.fn((cb: FrameRequestCallback) => {
  const id = ++rafId;
  const timeoutId = setTimeout(() => {
    rafCallbacks.delete(id);
    cb(Date.now());
  }, 16);
  rafCallbacks.set(id, timeoutId);
  return id;
}) as typeof global.requestAnimationFrame;

global.cancelAnimationFrame = vi.fn((id: number) => {
  const timeoutId = rafCallbacks.get(id);
  if (timeoutId) {
    clearTimeout(timeoutId);
    rafCallbacks.delete(id);
  }
}) as typeof global.cancelAnimationFrame;

// Mock devicePixelRatio
Object.defineProperty(window, 'devicePixelRatio', {
  writable: true,
  value: 1,
});

describe('AudioVisualizer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    rafCallbacks.clear();
    rafId = 0;
  });

  afterEach(() => {
    // Clean up any pending animation frames
    rafCallbacks.forEach((timeoutId) => clearTimeout(timeoutId));
    rafCallbacks.clear();
    cleanup();
  });

  it('renders canvas element', () => {
    render(<AudioVisualizer level={0.5} />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toBeInTheDocument();
    expect(canvas).toHaveAttribute('aria-label', 'Audio level visualizer');
  });

  it('renders with custom aria-label', () => {
    render(<AudioVisualizer level={0.5} ariaLabel="Custom label" />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toHaveAttribute('aria-label', 'Custom label');
  });

  it('renders with correct default height', () => {
    render(<AudioVisualizer level={0.5} />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toHaveStyle({ height: '60px' });
  });

  it('renders with custom height', () => {
    render(<AudioVisualizer level={0.5} height={100} />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toHaveStyle({ height: '100px' });
  });

  it('applies custom className', () => {
    render(<AudioVisualizer level={0.5} className="custom-class" />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toHaveClass('custom-class');
  });

  it('renders in bars variant', () => {
    render(<AudioVisualizer level={0.5} variant="bars" />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toBeInTheDocument();
  });

  it('renders in wave variant', () => {
    render(<AudioVisualizer level={0.5} variant="wave" />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toBeInTheDocument();
  });

  it('renders in circle variant', () => {
    render(<AudioVisualizer level={0.5} variant="circle" />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toBeInTheDocument();
  });

  it('renders with different color themes', () => {
    const { rerender } = render(<AudioVisualizer level={0.5} color="default" />);
    expect(screen.getByRole('img')).toBeInTheDocument();

    rerender(<AudioVisualizer level={0.5} color="success" />);
    expect(screen.getByRole('img')).toBeInTheDocument();

    rerender(<AudioVisualizer level={0.5} color="warning" />);
    expect(screen.getByRole('img')).toBeInTheDocument();

    rerender(<AudioVisualizer level={0.5} color="error" />);
    expect(screen.getByRole('img')).toBeInTheDocument();
  });

  it('renders with custom bar count', () => {
    render(<AudioVisualizer level={0.5} barCount={30} />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toBeInTheDocument();
  });

  it('renders with frequency data', () => {
    const frequencyData = new Array(64).fill(0).map((_, i) => i / 64);
    render(<AudioVisualizer level={0.5} frequencyData={frequencyData} />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toBeInTheDocument();
  });

  it('renders with isActive false', () => {
    render(<AudioVisualizer level={0.5} isActive={false} />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toBeInTheDocument();
  });

  it('handles zero level', () => {
    render(<AudioVisualizer level={0} />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toBeInTheDocument();
  });

  it('handles maximum level', () => {
    render(<AudioVisualizer level={1} />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toBeInTheDocument();
  });
});
