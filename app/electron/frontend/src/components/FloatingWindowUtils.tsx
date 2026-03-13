import type { CSSProperties } from 'react';

export type FloatingStyle = CSSProperties & { WebkitAppRegion?: string };

export function buttonStyle(variant: 'primary' | 'secondary', disabled = false): FloatingStyle {
  if (variant === 'primary') {
    return {
      WebkitAppRegion: 'no-drag',
      border: '1px solid rgba(74, 246, 38, 0.35)',
      background: disabled ? 'rgba(74, 246, 38, 0.15)' : 'rgba(74, 246, 38, 0.22)',
      color: disabled ? 'rgba(255,255,255,0.45)' : '#f5fff2',
      borderRadius: 10,
      padding: '8px 14px',
      fontSize: 13,
      fontWeight: 700,
      cursor: disabled ? 'not-allowed' : 'pointer',
    };
  }

  return {
    WebkitAppRegion: 'no-drag',
    border: '1px solid rgba(255,255,255,0.1)',
    background: 'rgba(255,255,255,0.06)',
    color: 'rgba(255,255,255,0.88)',
    borderRadius: 10,
    padding: '8px 14px',
    fontSize: 13,
    fontWeight: 700,
    cursor: 'pointer',
  };
}
