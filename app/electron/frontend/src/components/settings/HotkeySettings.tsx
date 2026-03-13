import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Keyboard,
  Check,
  X,
  AlertCircle,
  Play,
  RotateCcw,
  Info,
  Trash2,
  Circle,
} from 'lucide-react';
import type { HotkeyState } from '../../types/api';
import type { HotkeySettings } from '../../config/settingsSchema';

interface HotkeySettingsProps {
  onConfigChange?: (config: HotkeySettings) => void;
}

const KEY_DISPLAY_MAP: { [key: string]: string } = {
  Control: 'Ctrl',
  Shift: 'Shift',
  Alt: 'Alt',
  Meta: 'Win',
  ' ': 'Space',
  Space: 'Space',
  Enter: 'Enter',
  Escape: 'Esc',
  Tab: 'Tab',
  Backspace: 'Backspace',
  Delete: 'Del',
  ArrowUp: '↑',
  ArrowDown: '↓',
  ArrowLeft: '←',
  ArrowRight: '→',
  F1: 'F1',
  F2: 'F2',
  F3: 'F3',
  F4: 'F4',
  F5: 'F5',
  F6: 'F6',
  F7: 'F7',
  F8: 'F8',
  F9: 'F9',
  F10: 'F10',
  F11: 'F11',
  F12: 'F12',
};

const RECOMMENDED_HOTKEYS = [
  { combo: 'Ctrl+Shift+T', label: 'Ctrl+Shift+T', recommended: true },
  { combo: 'Ctrl+Shift+R', label: 'Ctrl+Shift+R', recommended: false },
  { combo: 'Ctrl+Alt+T', label: 'Ctrl+Alt+T', recommended: false },
  { combo: 'Ctrl+Alt+R', label: 'Ctrl+Alt+R', recommended: false },
];

const RESERVED_HOTKEYS = [
  'Ctrl+T',
  'Ctrl+R',
  'Ctrl+W',
  'Ctrl+N',
  'Ctrl+S',
  'Ctrl+C',
  'Ctrl+V',
  'Ctrl+X',
  'Ctrl+Z',
  'Ctrl+A',
  'Ctrl+F',
  'Ctrl+P',
  'F5',
  'F11',
  'F12',
];

// Language options for transcription
const LANGUAGE_OPTIONS = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' },
  { value: 'it', label: 'Italian' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'nl', label: 'Dutch' },
  { value: 'ja', label: 'Japanese' },
  { value: 'zh', label: 'Chinese' },
  { value: 'ko', label: 'Korean' },
  { value: 'ru', label: 'Russian' },
];

export function HotkeySettings({ onConfigChange }: HotkeySettingsProps) {
  const hotkeyApi = window.openwisprDesktop?.hotkey;

  const [hotkeyState, setHotkeyState] = useState<HotkeyState | null>(null);
  const [currentCombo, setCurrentCombo] = useState<string>('');
  const [isRecording, setIsRecording] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [isLoading, setIsLoading] = useState(true);

  // Quick settings state
  const [autoInject, setAutoInject] = useState(true);
  const [floatingWindow, setFloatingWindow] = useState(true);
  const [language, setLanguage] = useState('auto');

  const recordingRef = useRef(false);
  const keysPressedRef = useRef<Set<string>>(new Set());

  // Load initial state
  useEffect(() => {
    void loadHotkeyState();
  }, []);

  // Sync local state with hotkey state
  useEffect(() => {
    if (hotkeyState?.config) {
      setAutoInject(hotkeyState.config.auto_inject ?? true);
      setFloatingWindow(hotkeyState.config.show_floating_window ?? true);
      setLanguage(hotkeyState.config.language ?? 'auto');
    }
  }, [hotkeyState?.config]);

  const loadHotkeyState = async () => {
    if (!hotkeyApi?.getState) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const state = await hotkeyApi.getState();
      setHotkeyState(state);
      setCurrentCombo(state.config?.key_combination || '');
      setValidationError(state.error);
    } catch (err) {
      console.error('Failed to load hotkey state:', err);
      setValidationError('Failed to load hotkey state');
    } finally {
      setIsLoading(false);
    }
  };

  const formatKeyCombo = useCallback((combo: string): string => {
    if (!combo) return 'None';
    return combo
      .split('+')
      .map((key) => KEY_DISPLAY_MAP[key] || key)
      .join(' + ');
  }, []);

  const validateCombo = (combo: string): string | null => {
    if (!combo) {
      return 'Key combination is required';
    }

    const parts = combo.split('+');
    const hasModifier = parts.some(
      (p) => p === 'Control' || p === 'Alt' || p === 'Shift' || p === 'Meta'
    );
    const hasKey = parts.some(
      (p) => !['Control', 'Shift', 'Alt', 'Meta'].includes(p)
    );

    if (!hasModifier) {
      return 'Key combination must include a modifier key (Ctrl, Alt, Shift, or Win)';
    }

    if (!hasKey) {
      return 'Key combination must include a non-modifier key';
    }

    const normalized = combo.replace('Control', 'Ctrl').replace('Meta', 'Win');
    const reservedMatch = RESERVED_HOTKEYS.find(
      (r) => normalized === r || combo === r
    );
    if (reservedMatch) {
      return `"${reservedMatch}" is a reserved system hotkey and cannot be used`;
    }

    return null;
  };

  const startRecording = useCallback(() => {
    setIsRecording(true);
    recordingRef.current = true;
    keysPressedRef.current.clear();
    setValidationError(null);

    let timeoutId: number | null = null;

    const stopRecording = (capturedCombo?: string) => {
      if (!recordingRef.current) return;

      recordingRef.current = false;
      setIsRecording(false);

      window.removeEventListener('keydown', handleKeyDown, true);
      window.removeEventListener('keyup', handleKeyUp, true);
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
        timeoutId = null;
      }

      if (capturedCombo) {
        setCurrentCombo(capturedCombo);
        const error = validateCombo(capturedCombo);
        setValidationError(error);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (!recordingRef.current) return;

      e.preventDefault();
      e.stopPropagation();

      const keys = keysPressedRef.current;

      if (e.ctrlKey) keys.add('Control');
      if (e.shiftKey) keys.add('Shift');
      if (e.altKey) keys.add('Alt');
      if (e.metaKey) keys.add('Meta');

      if (!['Control', 'Shift', 'Alt', 'Meta'].includes(e.key)) {
        keys.add(e.key);
      }

      const hasModifier = e.ctrlKey || e.shiftKey || e.altKey || e.metaKey;
      const isFKey = /^F\d+$/.test(e.key);

      if ((hasModifier && keys.size >= 2) || isFKey) {
        const combo = Array.from(keys).join('+');
        stopRecording(combo);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (!recordingRef.current) return;

      if (!e.ctrlKey && !e.shiftKey && !e.altKey && !e.metaKey) {
        stopRecording();
      }
    };

    window.addEventListener('keydown', handleKeyDown, true);
    window.addEventListener('keyup', handleKeyUp, true);

    timeoutId = window.setTimeout(() => {
      if (recordingRef.current) {
        stopRecording();
      }
    }, 10000);

    const cleanup = () => {
      window.removeEventListener('keydown', handleKeyDown, true);
      window.removeEventListener('keyup', handleKeyUp, true);
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
        timeoutId = null;
      }
      if (recordingRef.current) {
        recordingRef.current = false;
      }
    };

    (window as unknown as Record<string, () => void>).__hotkeyRecordingCleanup = cleanup;

    return cleanup;
  }, []);

  useEffect(() => {
    return () => {
      const cleanup = (window as unknown as Record<string, () => void>).__hotkeyRecordingCleanup;
      if (cleanup) {
        cleanup();
        delete (window as unknown as Record<string, () => void>).__hotkeyRecordingCleanup;
      }
    };
  }, []);

  const selectRecommended = (combo: string) => {
    setCurrentCombo(combo);
    setValidationError(null);
  };

  const handleRegister = async () => {
    if (!hotkeyApi?.register || !currentCombo) return;

    const error = validateCombo(currentCombo);
    if (error) {
      setValidationError(error);
      return;
    }

    setIsValidating(true);
    setValidationError(null);

    try {
      const result = await hotkeyApi.register(currentCombo);
      if (result?.success) {
        await loadHotkeyState();
        if (onConfigChange && hotkeyState?.config) {
          onConfigChange({ ...hotkeyState.config, key_combination: currentCombo });
        }
      } else {
        setValidationError(result?.error || 'Failed to register hotkey');
      }
    } catch (err) {
      console.error('Failed to register hotkey:', err);
      setValidationError('Failed to register hotkey. The combination may be reserved by the system.');
    } finally {
      setIsValidating(false);
    }
  };

  const handleUnregister = async () => {
    if (!hotkeyApi?.unregister) return;

    try {
      await hotkeyApi.unregister();
      await loadHotkeyState();
    } catch (err) {
      console.error('Failed to unregister hotkey:', err);
    }
  };

  const handleTest = async () => {
    if (!hotkeyApi?.register || !currentCombo) return;

    const error = validateCombo(currentCombo);
    if (error) {
      setValidationError(error);
      return;
    }

    setTestStatus('testing');

    try {
      const result = await hotkeyApi.register(currentCombo);
      if (result?.success) {
        setTestStatus('success');
        await loadHotkeyState();
      } else {
        setTestStatus('error');
        setValidationError(result?.error || 'Hotkey test failed');
      }
    } catch (err) {
      console.error('Hotkey test failed:', err);
      setTestStatus('error');
      setValidationError('Hotkey test failed');
    }

    setTimeout(() => setTestStatus('idle'), 3000);
  };

  const handleClear = () => {
    setCurrentCombo('');
    setValidationError(null);
  };

  const handleQuickSettingChange = (
    key: keyof HotkeySettings,
    value: unknown
  ) => {
    if (onConfigChange && hotkeyState?.config) {
      onConfigChange({ ...hotkeyState.config, [key]: value });
    }
  };

  const getStatusColor = () => {
    if (hotkeyState?.session?.is_recording) return 'text-theme-success';
    if (hotkeyState?.is_registered) return 'text-lawn-accent';
    if (hotkeyState?.error) return 'text-error';
    return 'text-stone-500';
  };

  const getStatusText = () => {
    if (hotkeyState?.session?.is_recording) return 'Active - Currently recording';
    if (hotkeyState?.is_registered) return 'Registered - Ready to use';
    if (hotkeyState?.error) return `Error: ${hotkeyState.error}`;
    return 'Not registered';
  };

  if (isLoading) {
    return (
      <div className="border-2 border-lawn-border bg-lawn-panel p-6">
        <div className="flex items-center justify-center py-8">
          <div className="w-6 h-6 border-2 border-lawn-accent border-t-transparent rounded-full animate-spin" />
          <span className="ml-3 text-sm text-stone-500">Loading hotkey settings...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="border-2 border-lawn-border bg-lawn-panel p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Keyboard className="w-5 h-5 text-lawn-accent" />
          <h3 className="text-sm font-black uppercase tracking-wider text-lawn-border">
            Hotkey Mode Configuration
          </h3>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className={`font-bold ${getStatusColor()}`}>{getStatusText()}</span>
        </div>
      </div>

      {/* Mode Description */}
      <div className="flex items-start gap-3 p-3 border border-lawn-border bg-lawn-bg/50">
        <Info className="w-4 h-4 text-stone-500 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-stone-500">
          Hotkey Mode lets you activate transcription with a keyboard shortcut.
          Perfect for quick dictation while working in any application.
        </p>
      </div>

      {/* Current Hotkey Display */}
      <div className="border-2 border-lawn-border bg-lawn-bg p-4">
        <label className="block text-[10px] font-bold uppercase text-stone-500 mb-2">
          Current Hotkey
        </label>
        <div className="flex items-center justify-between">
          <span className="text-xl font-mono font-bold">
            {formatKeyCombo(hotkeyState?.config?.key_combination || currentCombo || 'None')}
          </span>
          {hotkeyState?.is_registered && (
            <Check className="w-5 h-5 text-theme-success" />
          )}
        </div>
      </div>

      {/* Recording Input */}
      <div className="space-y-3">
        <label className="block text-[10px] font-bold uppercase text-stone-500">
          Record New Hotkey
        </label>
        <div className="flex items-center gap-3">
          <button
            onClick={isRecording ? undefined : startRecording}
            className={`flex-1 border-2 px-4 py-3 text-center transition-all ${
              isRecording
                ? 'border-lawn-accent bg-lawn-accent/10 animate-pulse'
                : 'border-lawn-border bg-lawn-bg hover:border-lawn-accent/50'
            }`}
          >
            {isRecording ? (
              <span className="text-sm font-bold text-lawn-accent flex items-center justify-center gap-2">
                <Circle className="w-4 h-4 animate-pulse" />
                Press key combination...
              </span>
            ) : (
              <span className="text-sm font-bold">
                {currentCombo ? formatKeyCombo(currentCombo) : 'Click to record'}
              </span>
            )}
          </button>
          {currentCombo && (
            <button
              onClick={handleClear}
              className="p-3 border-2 border-lawn-border bg-lawn-bg hover:bg-error/10 hover:border-error transition-colors"
              title="Clear"
            >
              <Trash2 className="w-5 h-5" />
            </button>
          )}
        </div>
        <p className="text-xs text-stone-500">
          Press a key combination with at least one modifier (Ctrl, Alt, Shift, or Win)
        </p>
      </div>

      {/* Validation Error */}
      {validationError && (
        <div className="flex items-start gap-2 p-3 border-2 border-error bg-error/10 text-error text-xs">
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>{validationError}</span>
        </div>
      )}

      {/* Recommended Hotkeys */}
      <div className="space-y-3">
        <label className="block text-[10px] font-bold uppercase text-stone-500">
          Recommended Hotkeys
        </label>
        <div className="grid grid-cols-2 gap-2">
          {RECOMMENDED_HOTKEYS.map(({ combo, label, recommended }) => (
            <button
              key={combo}
              onClick={() => selectRecommended(combo)}
              className={`relative border-2 py-2 px-3 text-left transition-all ${
                currentCombo === combo
                  ? 'border-lawn-accent bg-lawn-accent/10'
                  : 'border-lawn-border bg-lawn-bg hover:border-lawn-accent/50'
              }`}
            >
              <span className="text-xs font-bold font-mono">{label}</span>
              {recommended && (
                <span className="absolute top-0 right-0 -mt-1 -mr-1 bg-lawn-accent text-lawn-bg text-[9px] px-1.5 py-0.5 font-bold uppercase">
                  Best
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Quick Settings */}
      <div className="border-t-2 border-lawn-border pt-4 space-y-4">
        <h4 className="text-[10px] font-bold uppercase text-stone-500">
          Quick Settings
        </h4>

        {/* Model Selection */}
        {/* Language Selection */}
        <div className="space-y-2">
          <label className="block text-xs font-bold text-lawn-border">
            Language
          </label>
          <select
            value={language}
            onChange={(e) => {
              const newLang = e.target.value;
              setLanguage(newLang);
              handleQuickSettingChange('language', newLang);
            }}
            className="w-full border-2 border-lawn-border bg-lawn-bg px-3 py-2 text-sm font-bold focus:border-lawn-accent focus:outline-none"
          >
            {LANGUAGE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Toggles Grid */}
        <div className="grid grid-cols-2 gap-3">
          {/* Auto-inject Toggle */}
          <div className="flex items-center justify-between p-3 border border-lawn-border bg-lawn-bg">
            <span className="text-xs font-bold">Auto-inject</span>
            <button
              onClick={() => {
                const newValue = !autoInject;
                setAutoInject(newValue);
                handleQuickSettingChange('auto_inject', newValue);
              }}
              role="switch"
              aria-checked={autoInject}
              aria-label="Auto-inject transcription"
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                autoInject ? 'bg-lawn-accent' : 'bg-stone-300'
              }`}
            >
              <span
                className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
                  autoInject ? 'translate-x-5' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Floating Window Toggle */}
          <div className="flex items-center justify-between p-3 border border-lawn-border bg-lawn-bg">
            <span className="text-xs font-bold">Floating Window</span>
            <button
              onClick={() => {
                const newValue = !floatingWindow;
                setFloatingWindow(newValue);
                handleQuickSettingChange('show_floating_window', newValue);
              }}
              role="switch"
              aria-checked={floatingWindow}
              aria-label="Show floating window"
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                floatingWindow ? 'bg-lawn-accent' : 'bg-stone-300'
              }`}
            >
              <span
                className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
                  floatingWindow ? 'translate-x-5' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={handleRegister}
          disabled={!currentCombo || isValidating || !!validationError}
          className="flex-1 border-2 border-lawn-accent bg-lawn-accent text-lawn-bg py-2 px-4 text-xs font-black uppercase tracking-wider hover:shadow-brutal-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isValidating ? (
            <>
              <div className="w-4 h-4 border-2 border-lawn-bg border-t-transparent rounded-full animate-spin" />
              Registering...
            </>
          ) : (
            <>
              <Check className="w-4 h-4" />
              Register Hotkey
            </>
          )}
        </button>
        <button
          onClick={handleTest}
          disabled={!currentCombo || isValidating}
          className={`border-2 py-2 px-4 text-xs font-black uppercase tracking-wider transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 ${
            testStatus === 'success'
              ? 'border-theme-success bg-theme-success text-lawn-bg'
              : testStatus === 'error'
              ? 'border-error bg-error text-lawn-bg'
              : 'border-lawn-border bg-lawn-bg hover:bg-lawn-accent hover:text-lawn-bg'
          }`}
        >
          {testStatus === 'testing' ? (
            <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : testStatus === 'success' ? (
            <Check className="w-4 h-4" />
          ) : testStatus === 'error' ? (
            <X className="w-4 h-4" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          {testStatus === 'success' ? 'OK' : testStatus === 'error' ? 'Failed' : 'Test'}
        </button>
        {hotkeyState?.is_registered && (
          <button
            onClick={handleUnregister}
            className="border-2 border-error text-error py-2 px-4 text-xs font-black uppercase tracking-wider hover:bg-error hover:text-lawn-bg transition-all"
          >
            Unregister
          </button>
        )}
      </div>

      {/* Status Section */}
      <div className="border-t-2 border-lawn-border pt-4 space-y-3">
        <h4 className="text-[10px] font-bold uppercase text-stone-500">Status Details</h4>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="border border-lawn-border bg-lawn-bg p-3">
            <span className="text-stone-500 block">Registration</span>
            <span
              className={`font-bold ${
                hotkeyState?.is_registered ? 'text-theme-success' : 'text-stone-500'
              }`}
            >
              {hotkeyState?.is_registered ? 'Registered' : 'Not Registered'}
            </span>
          </div>
          <div className="border border-lawn-border bg-lawn-bg p-3">
            <span className="text-stone-500 block">Active State</span>
            <span
              className={`font-bold ${
                hotkeyState?.session?.is_recording ? 'text-lawn-accent' : 'text-stone-500'
              }`}
            >
              {hotkeyState?.session?.is_recording ? 'Recording' : 'Idle'}
            </span>
          </div>
          {hotkeyState?.session?.total_activations !== undefined && (
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 block">Total Activations</span>
              <span className="font-bold">{hotkeyState.session.total_activations}</span>
            </div>
          )}
          {hotkeyState?.session?.last_activated_at && (
            <div className="border border-lawn-border bg-lawn-bg p-3">
              <span className="text-stone-500 block">Last Used</span>
              <span className="font-bold">
                {new Date(hotkeyState.session.last_activated_at).toLocaleTimeString()}
              </span>
            </div>
          )}
        </div>
        {hotkeyState?.error && (
          <div className="flex items-start gap-2 p-3 border-2 border-error bg-error/10 text-error text-xs">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Last Error:</span>
              <p>{hotkeyState.error}</p>
            </div>
          </div>
        )}
      </div>

      {/* Reset */}
      <div className="pt-2">
        <button
          onClick={loadHotkeyState}
          className="w-full border-2 border-lawn-border bg-lawn-bg py-2 text-xs font-bold uppercase text-stone-500 hover:text-lawn-border hover:border-lawn-border transition-all flex items-center justify-center gap-2"
        >
          <RotateCcw className="w-4 h-4" />
          Refresh State
        </button>
      </div>
    </div>
  );
}
