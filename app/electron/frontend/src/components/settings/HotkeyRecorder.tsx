import { useState } from 'react';
import { cn } from './utils';

interface HotkeyRecorderProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function HotkeyRecorder({ value, onChange, disabled = false }: HotkeyRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);

  const formatKeyCombo = (combo: string): string => {
    if (!combo) return 'None';
    const displayMap: Record<string, string> = {
      Control: 'Ctrl',
      Shift: 'Shift',
      Alt: 'Alt',
      Meta: 'Win',
      ' ': 'Space',
    };
    return combo
      .split('+')
      .map((key) => displayMap[key] || key)
      .join(' + ');
  };

  const startRecording = () => {
    if (disabled) return;
    setIsRecording(true);
    const keysPressed = new Set<string>();

    const handleKeyDown = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (e.ctrlKey) keysPressed.add('Control');
      if (e.shiftKey) keysPressed.add('Shift');
      if (e.altKey) keysPressed.add('Alt');
      if (e.metaKey) keysPressed.add('Meta');

      if (!['Control', 'Shift', 'Alt', 'Meta'].includes(e.key)) {
        keysPressed.add(e.key);
      }

      const hasModifier = e.ctrlKey || e.shiftKey || e.altKey || e.metaKey;
      const isFKey = /^F\d+$/.test(e.key);

      if ((hasModifier && keysPressed.size >= 2) || isFKey) {
        const combo = Array.from(keysPressed).join('+');
        stopRecording(combo);
      }
    };

    const handleKeyUp = () => {
      stopRecording();
    };

    const stopRecording = (capturedCombo?: string) => {
      setIsRecording(false);
      window.removeEventListener('keydown', handleKeyDown, true);
      window.removeEventListener('keyup', handleKeyUp, true);
      if (capturedCombo) {
        onChange(capturedCombo);
      }
    };

    window.addEventListener('keydown', handleKeyDown, true);
    window.addEventListener('keyup', handleKeyUp, true);

    setTimeout(() => stopRecording(), 10000);
  };

  return (
    <button
      onClick={isRecording ? undefined : startRecording}
      disabled={disabled}
      className={cn(
        'w-full border-2 px-4 py-3 text-center transition-all disabled:opacity-50 disabled:cursor-not-allowed',
        isRecording
          ? 'border-lawn-accent bg-lawn-accent/10 animate-pulse'
          : 'border-lawn-border bg-lawn-bg hover:border-lawn-accent/50'
      )}
    >
      {isRecording ? (
        <span className="text-sm font-bold text-lawn-accent">Press key combination...</span>
      ) : (
        <span className="text-sm font-mono font-bold">{formatKeyCombo(value)}</span>
      )}
    </button>
  );
}
