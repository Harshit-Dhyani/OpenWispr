import type {
  Device,
  ModelCatalogEntry,
  SystemProfile,
  OptimizationPreset,
} from '../../types/api';
import type { SettingsState, HotkeySettings } from '../../lib/settingsSchema';
import type { ModelManagerState } from '../../lib/modelRegistry';

export type SettingsCategory =
  | 'general'
  | 'models'
  | 'transcription'
  | 'audio'
  | 'hotkey'
  | 'coach'
  | 'history'
  | 'dictionary'
  | 'snippets'
  | 'style'
  | 'advanced';

export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

export interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  initialSettings?: SettingsState;
  onSettingsChange?: (settings: SettingsState) => void | Promise<void>;
  onSettingsReset?: () => void | Promise<void>;
  hardwareProfile?: SystemProfile;
  availableModels?: string[];
  modelManager?: ModelManagerState;
  onDownloadModel?: (modelId: string) => void | Promise<void>;
  onCancelModelDownload?: (modelId: string) => void | Promise<void>;
  onRemoveModel?: (modelId: string) => void | Promise<void>;
  availableLanguages?: string[];
  audioDevices?: Device[];
}

export interface SectionProps {
  settings: SettingsState;
  originalSettings: SettingsState;
  hardwareProfile?: SystemProfile;
  availableModels: string[];
  modelManager?: ModelManagerState;
  audioDevices: Device[];
  availableLanguages: string[];
  isChanged: (category: keyof SettingsState, key: string) => boolean;
  updateSetting: (category: keyof SettingsState, key: string, value: unknown) => void;
  resetSetting: (category: keyof SettingsState, key: string) => void;
  onDownloadModel?: (modelId: string) => void | Promise<void>;
  onCancelModelDownload?: (modelId: string) => void | Promise<void>;
  onRemoveModel?: (modelId: string) => void | Promise<void>;
}

export type {
  Device,
  ModelCatalogEntry,
  SystemProfile,
  OptimizationPreset,
  SettingsState,
  HotkeySettings,
  ModelManagerState,
};
