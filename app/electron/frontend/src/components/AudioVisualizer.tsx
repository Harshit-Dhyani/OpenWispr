import { useEffect, useRef, useCallback } from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type AudioVisualizerProps = {
  /** Audio level value from 0 to 1 */
  level: number;
  /** Array of frequency data for spectrum visualization */
  frequencyData?: number[] | null;
  /** Number of bars to display (default: 20) */
  barCount?: number;
  /** Height of the visualizer in pixels (default: 60) */
  height?: number;
  /** Whether the visualizer is active/recording */
  isActive?: boolean;
  /** Visual style variant */
  variant?: 'bars' | 'wave' | 'circle';
  /** Color theme */
  color?: 'default' | 'success' | 'warning' | 'error';
  /** Additional CSS classes */
  className?: string;
  /** ARIA label for accessibility */
  ariaLabel?: string;
};

export function AudioVisualizer({
  level,
  frequencyData,
  barCount = 20,
  height = 60,
  isActive = true,
  variant = 'bars',
  color = 'default',
  className,
  ariaLabel = 'Audio level visualizer',
}: AudioVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);
  const smoothedLevelRef = useRef(0);

  const getColor = useCallback((intensity: number, index?: number) => {
    const baseColors = {
      default: { r: 59, g: 130, b: 246 }, // blue-500
      success: { r: 34, g: 197, b: 94 }, // green-500
      warning: { r: 234, g: 179, b: 8 }, // yellow-500
      error: { r: 239, g: 68, b: 68 }, // red-500
    };

    const base = baseColors[color];
    const r = Math.min(255, base.r + intensity * 50);
    const g = Math.min(255, base.g + intensity * 30);
    const b = Math.min(255, base.b + (index !== undefined ? index * 5 : 0));
    
    return `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;
  }, [color]);

  const drawBars = useCallback((ctx: CanvasRenderingContext2D, width: number, height: number) => {
    const data = frequencyData || [];
    const barWidth = (width / barCount) * 0.8;
    const gap = (width / barCount) * 0.2;
    const centerY = height / 2;

    ctx.clearRect(0, 0, width, height);

    // Smooth the level value for fluid animation (60fps target)
    const targetLevel = isActive ? level : 0;
    smoothedLevelRef.current += (targetLevel - smoothedLevelRef.current) * 0.15;

    for (let i = 0; i < barCount; i++) {
      // Get frequency value for this bar, fallback to smoothed level
      const freqIndex = Math.floor((i / barCount) * data.length);
      const freqValue = data[freqIndex] || smoothedLevelRef.current;
      
      // Add some variation based on position for visual interest
      const positionFactor = 1 - Math.abs(i - barCount / 2) / (barCount / 2) * 0.3;
      const barHeight = Math.max(4, freqValue * height * 0.8 * positionFactor);

      const x = i * (barWidth + gap) + gap / 2;
      const y = centerY - barHeight / 2;

      // Create gradient for each bar
      const gradient = ctx.createLinearGradient(0, y + barHeight, 0, y);
      const intensity = freqValue;
      gradient.addColorStop(0, getColor(intensity * 0.5, i));
      gradient.addColorStop(1, getColor(intensity, i));

      ctx.fillStyle = gradient;
      
      // Draw rounded bar
      const radius = barWidth / 4;
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth, barHeight, radius);
      ctx.fill();
    }
  }, [frequencyData, barCount, level, isActive, getColor]);

  const drawWave = useCallback((ctx: CanvasRenderingContext2D, width: number, height: number) => {
    ctx.clearRect(0, 0, width, height);

    const targetLevel = isActive ? level : 0;
    smoothedLevelRef.current += (targetLevel - smoothedLevelRef.current) * 0.1;

    const centerY = height / 2;
    const amplitude = smoothedLevelRef.current * height * 0.4;
    const frequency = 0.02;
    const phase = Date.now() * 0.003;

    ctx.beginPath();
    ctx.strokeStyle = getColor(smoothedLevelRef.current);
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    for (let x = 0; x < width; x++) {
      const y = centerY + Math.sin(x * frequency + phase) * amplitude * Math.sin((x / width) * Math.PI);
      if (x === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.stroke();

    // Draw secondary wave
    ctx.beginPath();
    ctx.strokeStyle = getColor(smoothedLevelRef.current * 0.6);
    ctx.lineWidth = 2;
    
    for (let x = 0; x < width; x++) {
      const y = centerY + Math.sin(x * frequency * 1.5 + phase + 1) * amplitude * 0.7 * Math.sin((x / width) * Math.PI);
      if (x === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.stroke();
  }, [level, isActive, getColor]);

  const drawCircle = useCallback((ctx: CanvasRenderingContext2D, width: number, height: number) => {
    ctx.clearRect(0, 0, width, height);

    const targetLevel = isActive ? level : 0;
    smoothedLevelRef.current += (targetLevel - smoothedLevelRef.current) * 0.1;

    const centerX = width / 2;
    const centerY = height / 2;
    const baseRadius = Math.min(width, height) * 0.25;
    const pulseRadius = baseRadius + smoothedLevelRef.current * baseRadius * 0.5;

    // Draw outer pulse rings
    for (let i = 3; i >= 0; i--) {
      const ringRadius = pulseRadius + i * 8;
      const alpha = (1 - i * 0.2) * smoothedLevelRef.current * 0.5;
      
      ctx.beginPath();
      ctx.arc(centerX, centerY, ringRadius, 0, Math.PI * 2);
      ctx.strokeStyle = getColor(smoothedLevelRef.current * (1 - i * 0.2));
      ctx.lineWidth = 2;
      ctx.globalAlpha = alpha;
      ctx.stroke();
    }

    ctx.globalAlpha = 1;

    // Draw main circle
    const gradient = ctx.createRadialGradient(
      centerX, centerY, 0,
      centerX, centerY, pulseRadius
    );
    gradient.addColorStop(0, getColor(smoothedLevelRef.current));
    gradient.addColorStop(1, getColor(smoothedLevelRef.current * 0.3));

    ctx.beginPath();
    ctx.arc(centerX, centerY, pulseRadius, 0, Math.PI * 2);
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw inner dot
    ctx.beginPath();
    ctx.arc(centerX, centerY, baseRadius * 0.3, 0, Math.PI * 2);
    ctx.fillStyle = getColor(1);
    ctx.fill();
  }, [level, isActive, getColor]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Handle high-DPI displays
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const animate = () => {
      switch (variant) {
        case 'bars':
          drawBars(ctx, rect.width, rect.height);
          break;
        case 'wave':
          drawWave(ctx, rect.width, rect.height);
          break;
        case 'circle':
          drawCircle(ctx, rect.width, rect.height);
          break;
      }
      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [variant, drawBars, drawWave, drawCircle]);

  return (
    <canvas
      ref={canvasRef}
      className={cn('w-full rounded-md bg-lawn-bg/50', className)}
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
    />
  );
}

export default AudioVisualizer;
