import { useState } from 'react';
import { cn } from './utils';

interface HotkeyRecorderProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

const MODIFIER_KEYS = new Set(['Control', 'Shift', 'Alt', 'Meta']);

const DISPLAY_MAP: Record<string, string> = {
  CommandOrControl: 'Ctrl',
  Control: 'Ctrl',
  Ctrl: 'Ctrl',
  Shift: 'Shift',
  Alt: 'Alt',
  Super: 'Win',
  Meta: 'Win',
  Command: 'Cmd',
  ' ': 'Space',
};

const KEY_NAME_MAP: Record<string, string> = {
  ' ': 'Space',
  Spacebar: 'Space',
  ArrowUp: 'Up',
  ArrowDown: 'Down',
  ArrowLeft: 'Left',
  ArrowRight: 'Right',
  Escape: 'Escape',
  Esc: 'Escape',
  Enter: 'Enter',
  Return: 'Enter',
  Tab: 'Tab',
  Backspace: 'Backspace',
  Delete: 'Delete',
  Del: 'Delete',
  Insert: 'Insert',
  Home: 'Home',
  End: 'End',
  PageUp: 'PageUp',
  PageDown: 'PageDown',
  Plus: 'Plus',
};

function normalizeKeyName(key: string): string | null {
  if (!key || MODIFIER_KEYS.has(key)) {
    return null;
  }

  if (KEY_NAME_MAP[key]) {
    return KEY_NAME_MAP[key];
  }

  if (/^F\d{1,2}$/i.test(key)) {
    return key.toUpperCase();
  }

  if (/^[a-z]$/i.test(key)) {
    return key.toUpperCase();
  }

  if (/^[0-9]$/.test(key)) {
    return key;
  }

  if (key.length === 1) {
    return key.toUpperCase();
  }

  return key;
}

export function normalizeAcceleratorFromKeyboardEvent(event: KeyboardEvent): string | null {
  const parts: string[] = [];

  if (event.ctrlKey) {
    parts.push('CommandOrControl');
  }
  if (event.altKey) {
    parts.push('Alt');
  }
  if (event.shiftKey) {
    parts.push('Shift');
  }
  if (event.metaKey) {
    parts.push('Super');
  }

  const keyName = normalizeKeyName(event.key);
  if (keyName) {
    parts.push(keyName);
  }

  if (parts.length === 0) {
    return null;
  }

  if (parts.length === 1 && !/^F\d{1,2}$/i.test(parts[0])) {
    return null;
  }

  return parts.join('+');
}

export function formatHotkeyCombo(combo: string): string {
  if (!combo) {
    return 'None';
  }

  return combo
    .split('+')
    .map((key) => DISPLAY_MAP[key] || key)
    .join('+');
}

export function HotkeyRecorder({ value, onChange, disabled = false }: HotkeyRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);

  const startRecording = () => {
    if (disabled) return;
    setIsRecording(true);

    const handleKeyDown = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();

      const combo = normalizeAcceleratorFromKeyboardEvent(e);
      if (combo) {
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
        <span className="text-sm font-mono font-bold">{formatHotkeyCombo(value)}</span>
      )}
    </button>
  );
}
