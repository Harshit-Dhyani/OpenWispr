/// <reference types="vite/client" />

declare global {
  interface Window {
    openwisprDesktop: {
      // File system APIs
      chooseDirectory: () => Promise<string | null>;
      choosePdf: () => Promise<string | null>;

      // Backend lifecycle
      onBackendExit: (callback: () => void) => () => void;
      onOpenSettings: (callback: () => void) => () => void;
      onSettingsUpdated: (callback: () => void) => () => void;

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
        start: (source?: 'microphone' | 'system') => Promise<unknown>;
        stop: () => Promise<unknown>;
        register: (accelerator: string) => Promise<{ success: boolean; error?: string }>;
        unregister: () => Promise<{ success: boolean; error?: string }>;
        getState: () => Promise<{
          config: import('./config/settingsSchema').HotkeySettings;
          session: import('./types/api').HotkeySession | null;
          is_registered: boolean;
          error: string | null;
        }>;
        onStateChange: (callback: (event: unknown, state: import('./types/api').HotkeyState) => void) => void;
        onTranscriptEvent: (
          callback: (payload: {
            type: string;
            payload: import('./types/api').DraftPartialPayload | import('./types/api').CommitFinalPayload | Record<string, unknown>;
          }) => void
        ) => () => void;
        removeStateChangeListener: (callback: (event: unknown, state: import('./types/api').HotkeyState) => void) => void;
        updateConfig: (config: Partial<import('./config/settingsSchema').HotkeySettings>) => Promise<{ success: boolean; config?: import('./config/settingsSchema').HotkeySettings; error?: string }>;
      };
      applyHotkeyConfig: (hotkeyConfig: import('./config/settingsSchema').HotkeySettings) => Promise<unknown>;

      // Text injection
      text?: {
        inject: (text: string) => Promise<void>;
      };

      // Floating window control
      floatingWindow?: {
        show?: () => Promise<unknown>;
        hide?: () => Promise<unknown>;
        updatePosition?: (position: import('./config/settingsSchema').HotkeySettings['floating_window_position']) => Promise<void>;
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
    openwisprFloating?: {
      onRecordingState: (
        callback: (state: {
          isRecording: boolean;
          processing?: boolean;
          finished?: boolean;
          sessionId?: string | null;
          mode?: string;
          error?: string | null;
        }) => void
      ) => () => void;
      onTranscription: (
        callback: (data: {
          text?: string;
          committedText?: string;
          partialText?: string;
          isPartial?: boolean;
          sessionId?: string | null;
          segmentIndex?: number | null;
          mode?: string;
        } | string) => void
      ) => () => void;
      onAudioVisualizer: (callback: (data: { levels: number[]; peak: number }) => void) => () => void;
      onHotkeyEvent: (callback: (event: { type: 'start' | 'stop' }) => void) => () => void;
      onCoachResult?: (callback: (payload: import('./types/api').HotkeyStopResponse | null) => void) => () => void;
      onCoachResultClear?: (callback: () => void) => () => void;
      onModelPreparation?: (
        callback: (payload: {
          active: boolean;
          stage?: 'idle' | 'loading' | 'ready' | 'error';
          message?: string;
          modelName?: string | null;
          sessionId?: string | null;
        }) => void
      ) => () => void;
      cancelRecording?: () => void;
      finishRecording?: () => void;
      finishAndPaste?: () => void;
      dismissResult?: () => void;
      platform: string;
      debugEnabled?: boolean;
      settings?: {
        showFloatingCoachResult?: boolean;
      };
      strings?: {
        status?: Record<string, string>;
        waitingForSpeech?: string;
        actions?: Record<string, string>;
        resultMeta?: Record<string, string>;
        modelPrep?: Record<string, string>;
      };
    };
  }
}

export {};
