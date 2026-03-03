/// <reference types="vite/client" />

declare global {
  interface Window {
    transcriptaDesktop: {
      // File system APIs
      chooseDirectory: () => Promise<string | null>;
      choosePdf: () => Promise<string | null>;

      // Backend lifecycle
      onBackendExit: (callback: () => void) => () => void;
      onOpenSettings: (callback: () => void) => () => void;

      // HTTP API wrapper
      getApiOrigin: () => Promise<string>;
      fetchJson: (path: string, options?: RequestInit) => Promise<unknown>;
      models: {
        getDownloadRoot: () => Promise<string>;
        download: (modelId: string) => Promise<unknown>;
        cancel: (modelId: string) => Promise<unknown>;
        remove: (modelId: string) => Promise<unknown>;
        onDownloadEvent: (
          callback: (payload: {
            event: string;
            payload: import('./types/api').ModelDownloadState | { model_id: string };
          }) => void
        ) => () => void;
      };

      // Hotkey management
      hotkey: {
        toggle: (enabled: boolean) => Promise<unknown>;
        register: (accelerator: string) => Promise<{ success: boolean; error?: string }>;
        unregister: () => Promise<{ success: boolean; error?: string }>;
        getState: () => Promise<{
          config: import('./lib/settingsSchema').HotkeySettings;
          session: import('./types/api').HotkeySession | null;
          is_registered: boolean;
          error: string | null;
        }>;
        onStateChange: (callback: (event: unknown, state: import('./types/api').HotkeyState) => void) => void;
        removeStateChangeListener: (callback: (event: unknown, state: import('./types/api').HotkeyState) => void) => void;
        updateConfig: (config: Partial<import('./lib/settingsSchema').HotkeySettings>) => Promise<{ success: boolean; config?: import('./lib/settingsSchema').HotkeySettings; error?: string }>;
      };

      // Text injection
      text?: {
        inject: (text: string) => Promise<void>;
      };

      // Floating window control
      floatingWindow?: {
        show?: () => Promise<unknown>;
        hide?: () => Promise<unknown>;
        updatePosition?: (position: import('./lib/settingsSchema').HotkeySettings['floating_window_position']) => Promise<void>;
        updateOptions?: (options: Partial<import('./types/api').FloatingWindowOptions>) => Promise<void>;
      };

      // Tray
      tray?: {
        updateTooltip: (tooltip: string) => Promise<void>;
      };

      // Platform info
      platform: string;

      // Version info
      versions: {
        node: string;
        electron: string;
        chrome: string;
      };

      // Floating window event handlers (set by floating window)
      onAudioLevel?: (event: unknown, data: number[]) => void;
      onTranscription?: (event: unknown, text: string) => void;
      onRecordingStateChange?: (event: unknown, state: 'idle' | 'listening' | 'processing') => void;
    };
    transcriptaFloating?: {
      onRecordingState: (
        callback: (state: { isRecording: boolean; processing?: boolean; finished?: boolean }) => void
      ) => () => void;
      onTranscription: (
        callback: (data: { text?: string; isPartial?: boolean } | string) => void
      ) => () => void;
      onAudioVisualizer: (callback: (data: { levels: number[]; peak: number }) => void) => () => void;
      onHotkeyEvent: (callback: (event: { type: 'start' | 'stop' }) => void) => () => void;
      platform: string;
    };
  }
}

export {};
