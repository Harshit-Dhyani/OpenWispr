import {
  Settings,
  Bot,
  Mic,
  Volume2,
  Keyboard,
  Cpu,
} from 'lucide-react';
import type { SettingsCategory } from './types';

export const CATEGORIES: {
  id: SettingsCategory;
  label: string;
  icon: React.ElementType;
  description: string;
}[] = [
  {
    id: 'general',
    label: 'General',
    icon: Settings,
    description: 'Session defaults, language, export location',
  },
  {
    id: 'models',
    label: 'Models',
    icon: Bot,
    description: 'Download, verify, and select ASR and refiner models',
  },
  {
    id: 'transcription',
    label: 'Transcription',
    icon: Mic,
    description: 'Model, quality, performance settings',
  },
  {
    id: 'audio',
    label: 'Audio',
    icon: Volume2,
    description: 'VAD, noise filtering, audio devices',
  },
  {
    id: 'hotkey',
    label: 'Hotkey',
    icon: Keyboard,
    description: 'Global hotkey configuration',
  },
  {
    id: 'advanced',
    label: 'Advanced',
    icon: Cpu,
    description: 'Expert settings, developer options',
  },
];
