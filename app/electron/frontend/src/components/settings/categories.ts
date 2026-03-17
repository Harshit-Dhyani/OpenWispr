import {
  Settings,
  Bot,
  Mic,
  Volume2,
  Keyboard,
  Cpu,
  Sparkles,
  History,
  BookText,
  ScissorsSquareDashedBottom,
  Paintbrush,
} from 'lucide-react';
import type { SettingsCategory } from './types';
import { RENDERER_STRINGS } from '../../strings/en';

export const CATEGORIES: {
  id: SettingsCategory;
  label: string;
  icon: React.ElementType;
  description: string;
}[] = [
  {
    id: 'models',
    label: RENDERER_STRINGS.settings.categories.models.label,
    icon: Bot,
    description: RENDERER_STRINGS.settings.categories.models.description,
  },
  {
    id: 'general',
    label: RENDERER_STRINGS.settings.categories.general.label,
    icon: Settings,
    description: RENDERER_STRINGS.settings.categories.general.description,
  },
  {
    id: 'transcription',
    label: RENDERER_STRINGS.settings.categories.transcription.label,
    icon: Mic,
    description: RENDERER_STRINGS.settings.categories.transcription.description,
  },
  {
    id: 'audio',
    label: RENDERER_STRINGS.settings.categories.audio.label,
    icon: Volume2,
    description: RENDERER_STRINGS.settings.categories.audio.description,
  },
  {
    id: 'hotkey',
    label: RENDERER_STRINGS.settings.categories.hotkey.label,
    icon: Keyboard,
    description: RENDERER_STRINGS.settings.categories.hotkey.description,
  },
  {
    id: 'coach',
    label: RENDERER_STRINGS.settings.categories.coach.label,
    icon: Sparkles,
    description: RENDERER_STRINGS.settings.categories.coach.description,
  },
  {
    id: 'history',
    label: RENDERER_STRINGS.settings.categories.history.label,
    icon: History,
    description: RENDERER_STRINGS.settings.categories.history.description,
  },
  {
    id: 'dictionary',
    label: RENDERER_STRINGS.settings.categories.dictionary.label,
    icon: BookText,
    description: RENDERER_STRINGS.settings.categories.dictionary.description,
  },
  {
    id: 'snippets',
    label: RENDERER_STRINGS.settings.categories.snippets.label,
    icon: ScissorsSquareDashedBottom,
    description: RENDERER_STRINGS.settings.categories.snippets.description,
  },
  {
    id: 'style',
    label: RENDERER_STRINGS.settings.categories.style.label,
    icon: Paintbrush,
    description: RENDERER_STRINGS.settings.categories.style.description,
  },
  {
    id: 'advanced',
    label: RENDERER_STRINGS.settings.categories.advanced.label,
    icon: Cpu,
    description: RENDERER_STRINGS.settings.categories.advanced.description,
  },
];
