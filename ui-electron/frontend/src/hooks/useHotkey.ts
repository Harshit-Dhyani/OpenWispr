import { useState, useEffect, useCallback, useRef } from 'react';
import type { HotkeyState, HotkeyConfig, HotkeyStatus } from '../types/api';

export type HotkeyEvent = {
  type: 'activated' | 'deactivated' | 'text_ready' | 'error' | 'state_change';
  payload: unknown;
  timestamp: string;
};

export type UseHotkeyOptions = {
  onActivated?: () => void;
  onDeactivated?: () => void;
  onTextReady?: (text: string) => void;
  onError?: (error: string) => void;
  onStateChange?: (state: HotkeyState) => void;
};

export type UseHotkeyReturn = {
  state: HotkeyState | null;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  enableHotkey: () => Promise<void>;
  disableHotkey: () => Promise<void>;
  toggleHotkey: () => Promise<void>;
  updateConfig: (config: Partial<HotkeyConfig>) => Promise<void>;
  testHotkey: () => Promise<void>;
  showFloatingWindow: () => Promise<void>;
  hideFloatingWindow: () => Promise<void>;
  
  // State helpers
  isEnabled: boolean;
  isActive: boolean;
  status: HotkeyStatus;
  currentText: string;
};

export function useHotkey(options: UseHotkeyOptions = {}): UseHotkeyReturn {
  const { onActivated, onDeactivated, onTextReady, onError, onStateChange } = options;
  
  const [state, setState] = useState<HotkeyState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const stateRef = useRef(state);
  const hotkeyApi = window.transcriptaDesktop.hotkey;
  
  // Keep ref in sync with state for event handlers
  useEffect(() => {
    stateRef.current = state;
  }, [state]);
  
  // Fetch initial hotkey state
  const loadState = useCallback(async () => {
    try {
      setIsLoading(true);
      const result = await hotkeyApi.getState();
      setState(result as HotkeyState);
      setError(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load hotkey state';
      setError(errorMessage);
      console.error('Failed to load hotkey state:', err);
    } finally {
      setIsLoading(false);
    }
  }, [hotkeyApi]);
  
  // Initial load
  useEffect(() => {
    void loadState();
  }, [loadState]);
  
  // Listen for hotkey state changes from main process
  useEffect(() => {
    const handleStateChange = (_event: unknown, statePayload: unknown) => {
      const newState = statePayload as HotkeyState;
      setState(newState);
      onStateChange?.(newState);
      
      // Trigger callbacks based on state changes
      const oldStatus = stateRef.current?.session?.status;
      const newStatus = newState.session?.status;
      
      if (oldStatus !== 'listening' && newStatus === 'listening') {
        onActivated?.();
      }
      
      if (oldStatus === 'listening' && newStatus !== 'listening') {
        onDeactivated?.();
      }
      
      if (newState.session?.current_text && newState.session.current_text !== stateRef.current?.session?.current_text) {
        onTextReady?.(newState.session.current_text);
      }
      
      if (newState.error) {
        onError?.(newState.error);
      }
    };
    
    hotkeyApi.onStateChange(handleStateChange);
    
    return () => {
      hotkeyApi.removeStateChangeListener(handleStateChange);
    };
  }, [hotkeyApi, onActivated, onDeactivated, onTextReady, onError, onStateChange]);
  
  // Enable hotkey
  const enableHotkey = useCallback(async () => {
    try {
      setIsLoading(true);
      await hotkeyApi.toggle(true);
      await loadState();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to enable hotkey';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [hotkeyApi, loadState]);
  
  // Disable hotkey
  const disableHotkey = useCallback(async () => {
    try {
      setIsLoading(true);
      await hotkeyApi.toggle(false);
      await loadState();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to disable hotkey';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [hotkeyApi, loadState]);
  
  // Toggle hotkey
  const toggleHotkey = useCallback(async () => {
    if (state?.config.enabled) {
      await disableHotkey();
    } else {
      await enableHotkey();
    }
  }, [state?.config.enabled, enableHotkey, disableHotkey]);
  
  // Update config
  const updateConfig = useCallback(async (config: Partial<HotkeyConfig>) => {
    try {
      setIsLoading(true);
      const result = await window.transcriptaDesktop.fetchJson('/api/hotkey/config', {
        method: 'POST',
        body: JSON.stringify({ config }),
      });
      setState(result as HotkeyState);
      setError(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update config';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  // Show floating window
  const showFloatingWindow = useCallback(async () => {
    try {
      await window.transcriptaDesktop.floatingWindow?.show?.();
    } catch (err) {
      console.error('Failed to show floating window:', err);
    }
  }, []);
  
  // Hide floating window
  const hideFloatingWindow = useCallback(async () => {
    try {
      await window.transcriptaDesktop.floatingWindow?.hide?.();
    } catch (err) {
      console.error('Failed to hide floating window:', err);
    }
  }, []);

  // Test hotkey (shows floating window)
  const testHotkey = useCallback(async () => {
    try {
      await hotkeyApi.toggle(true);
      await showFloatingWindow();

      setTimeout(() => {
        void hideFloatingWindow();
      }, 3000);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to test hotkey';
      setError(errorMessage);
      throw err;
    }
  }, [hotkeyApi, showFloatingWindow, hideFloatingWindow]);
  
  // Computed values
  const isEnabled = state?.config.enabled ?? false;
  const isActive = state?.session?.is_active ?? false;
  const status = state?.session?.status ?? 'idle';
  const currentText = state?.session?.current_text ?? '';
  
  return {
    state,
    isLoading,
    error,
    
    // Actions
    enableHotkey,
    disableHotkey,
    toggleHotkey,
    updateConfig,
    testHotkey,
    showFloatingWindow,
    hideFloatingWindow,
    
    // State helpers
    isEnabled,
    isActive,
    status,
    currentText,
  };
}
