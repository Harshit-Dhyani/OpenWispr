# Architecture Plan: Auto-Optimization, Advanced Settings & Global Hotkey

**Status**: Design Document  
**Scope**: V2 Features - Post-MVP Enhancement  
**Platform**: Windows 11 (primary), cross-platform fallback

---

## 1. Auto-Optimization System

### 1.1 PC Specs Detection

```python
# app/optimizer/profiler.py

from dataclasses import dataclass
from typing import Optional
import torch
import psutil
import cpuinfo

@dataclass
class GPUProfile:
    name: str
    vram_gb: float
    compute_capability: tuple[int, int]
    max_model_size: str
    compute_type: str
    can_run_large: bool

@dataclass
class CPUProfile:
    cores: int
    logical_cores: int
    ram_gb: float
    has_avx2: bool
    max_workers: int
    use_parallel: bool

@dataclass
class StorageProfile:
    free_gb: float
    is_ssd: bool
    can_download_large_models: bool

@dataclass
class SystemProfile:
    gpu: Optional[GPUProfile]
    cpu: CPUProfile
    storage: StorageProfile


class SystemProfiler:
    """Detects system capabilities and recommends optimal settings."""
    
    def analyze_gpu(self) -> Optional[GPUProfile]:
        if not torch.cuda.is_available():
            return None
            
        props = torch.cuda.get_device_properties(0)
        vram_gb = props.total_memory / (1024**3)
        
        # Map VRAM to model capability
        if vram_gb >= 10:
            max_model = "large-v3"
            compute = "float16"
            can_large = True
        elif vram_gb >= 8:
            max_model = "large-v3"
            compute = "int8"
            can_large = True
        elif vram_gb >= 6:
            max_model = "medium"
            compute = "float16"
            can_large = False
        elif vram_gb >= 4:
            max_model = "small"
            compute = "float16"
            can_large = False
        else:
            max_model = "base"
            compute = "int8"
            can_large = False
        
        return GPUProfile(
            name=props.name,
            vram_gb=vram_gb,
            compute_capability=(props.major, props.minor),
            max_model_size=max_model,
            compute_type=compute,
            can_run_large=can_large
        )
    
    def analyze_cpu(self) -> CPUProfile:
        info = cpuinfo.get_cpu_info()
        ram = psutil.virtual_memory()
        
        flags = info.get("flags", [])
        has_avx2 = "avx2" in flags
        
        # Workers: physical cores for Whisper, leave headroom
        cores = psutil.cpu_count(logical=False) or 4
        max_workers = max(1, cores - 1)
        
        return CPUProfile(
            cores=cores,
            logical_cores=psutil.cpu_count(logical=True) or cores,
            ram_gb=ram.total / (1024**3),
            has_avx2=has_avx2,
            max_workers=max_workers,
            use_parallel=cores >= 4
        )
    
    def analyze_storage(self) -> StorageProfile:
        disk = psutil.disk_usage(".")
        free_gb = disk.free / (1024**3)
        
        # SSD detection via Windows WMI
        is_ssd = self._detect_ssd_windows()
        
        return StorageProfile(
            free_gb=free_gb,
            is_ssd=is_ssd,
            can_download_large_models=free_gb >= 15
        )
    
    def _detect_ssd_windows(self) -> bool:
        try:
            import wmi
            c = wmi.WMI()
            for disk in c.Win32_DiskDrive():
                if "SSD" in disk.Model or disk.MediaType == "SSD":
                    return True
            return False
        except:
            return True  # Assume SSD if detection fails
    
    def get_full_profile(self) -> SystemProfile:
        return SystemProfile(
            gpu=self.analyze_gpu(),
            cpu=self.analyze_cpu(),
            storage=self.analyze_storage()
        )
```

### 1.2 Auto-Config Generation

```python
# app/optimizer/auto_optimizer.py

from dataclasses import dataclass
from typing import Literal

@dataclass
class OptimizedConfig:
    model: str
    compute_type: Literal["int8", "float16", "float32"]
    chunk_duration: float
    overlap_ratio: float
    vad_enabled: bool
    vad_threshold: float
    quality_threshold: float
    beam_size: int
    best_of: int
    device: Literal["cuda", "cpu"]
    workers: int


class AutoOptimizer:
    """Generates optimal settings based on hardware profile."""
    
    MODEL_SIZES = {
        "tiny": 0.039,
        "base": 0.074,
        "small": 0.244,
        "medium": 0.769,
        "large-v3": 2.87
    }
    
    def __init__(self, profile: SystemProfile):
        self.profile = profile
    
    def generate_config(self) -> OptimizedConfig:
        gpu = self.profile.gpu
        cpu = self.profile.cpu
        
        if gpu:
            return self._gpu_optimized_config(gpu)
        else:
            return self._cpu_optimized_config(cpu)
    
    def _gpu_optimized_config(self, gpu: GPUProfile) -> OptimizedConfig:
        # Model already determined by VRAM analysis
        model = gpu.max_model_size
        compute = gpu.compute_type
        
        # Chunk duration: smaller = lower latency but more overhead
        if model in ["tiny", "base"]:
            chunk_duration = 0.2
        elif model in ["small", "medium"]:
            chunk_duration = 0.5
        else:  # large-v3
            chunk_duration = 1.0
        
        # Quality threshold balances accuracy vs silence
        quality_threshold = 0.65 if model in ["tiny", "base"] else 0.70
        
        return OptimizedConfig(
            model=model,
            compute_type=compute,
            chunk_duration=chunk_duration,
            overlap_ratio=0.1,
            vad_enabled=True,
            vad_threshold=-40.0,
            quality_threshold=quality_threshold,
            beam_size=5,
            best_of=5,
            device="cuda",
            workers=1  # GPU uses 1 worker
        )
    
    def _cpu_optimized_config(self, cpu: CPUProfile) -> OptimizedConfig:
        # CPU fallback: smaller model, more workers
        if cpu.ram_gb >= 16:
            model = "medium"
        elif cpu.ram_gb >= 8:
            model = "small"
        else:
            model = "base"
        
        return OptimizedConfig(
            model=model,
            compute_type="int8",
            chunk_duration=1.0,
            overlap_ratio=0.0,
            vad_enabled=True,
            vad_threshold=-40.0,
            quality_threshold=0.60,
            beam_size=1,
            best_of=1,
            device="cpu",
            workers=cpu.max_workers
        )
    
    def get_recommended_settings(self) -> dict:
        config = self.generate_config()
        return {
            "model": config.model,
            "compute_type": config.compute_type,
            "chunk_duration": config.chunk_duration,
            "vad_enabled": config.vad_enabled,
            "quality_threshold": config.quality_threshold,
            "device": config.device,
            "workers": config.workers
        }
    
    def meets_minimum_specs(self) -> tuple[bool, list[str]]:
        issues = []
        cpu = self.profile.cpu
        storage = self.profile.storage
        
        if cpu.cores < 4:
            issues.append(f"CPU cores ({cpu.cores}) below minimum (4)")
        
        if cpu.ram_gb < 8:
            issues.append(f"RAM ({cpu.ram_gb:.1f}GB) below minimum (8GB)")
        
        if storage.free_gb < 10:
            issues.append(f"Free space ({storage.free_gb:.1f}GB) below minimum (10GB)")
        
        return len(issues) == 0, issues
```

### 1.3 Settings Migration

```python
# app/optimizer/migration.py

import json
from pathlib import Path
from typing import Any

class SettingsMigration:
    """Handles migration from old settings to auto-optimized settings."""
    
    SETTINGS_FILE = Path("data/settings.json")
    BACKUP_DIR = Path("data/backups")
    
    def __init__(self):
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    def migrate_if_needed(self) -> dict[str, Any]:
        """Check if migration is needed and perform it."""
        if not self.SETTINGS_FILE.exists():
            return self._create_fresh_config()
        
        current = json.loads(self.SETTINGS_FILE.read_text())
        
        # Check if already using auto-optimization
        if current.get("auto_optimized", False):
            return current
        
        # Backup old settings
        self._backup_settings(current)
        
        # Generate new optimized config
        profiler = SystemProfiler()
        profile = profiler.get_full_profile()
        optimizer = AutoOptimizer(profile)
        
        optimized = optimizer.generate_config()
        
        # Merge with user preferences (preserve non-performance settings)
        migrated = {
            **current,
            "model": optimized.model,
            "compute_type": optimized.compute_type,
            "chunk_duration": optimized.chunk_duration,
            "device": optimized.device,
            "workers": optimized.workers,
            "vad_enabled": optimized.vad_enabled,
            "vad_threshold": optimized.vad_threshold,
            "quality_threshold": optimized.quality_threshold,
            "beam_size": optimized.beam_size,
            "best_of": optimized.best_of,
            "auto_optimized": True,
            "optimization_date": datetime.now().isoformat(),
            "hardware_profile": {
                "gpu": self.profile.gpu.__dict__ if self.profile.gpu else None,
                "cpu_cores": self.profile.cpu.cores,
                "ram_gb": self.profile.cpu.ram_gb,
                "storage_ssd": self.profile.storage.is_ssd
            }
        }
        
        self._save_settings(migrated)
        return migrated
    
    def _create_fresh_config(self) -> dict[str, Any]:
        """Generate initial config for new users."""
        profiler = SystemProfiler()
        profile = profiler.get_full_profile()
        optimizer = AutoOptimizer(profile)
        
        config = optimizer.generate_config()
        
        return {
            "model": config.model,
            "compute_type": config.compute_type,
            "chunk_duration": config.chunk_duration,
            "device": config.device,
            "vad_enabled": config.vad_enabled,
            "auto_optimized": True,
            "first_run": True
        }
```

---

## 2. Advanced Settings Panel

### 2.1 TypeScript Interfaces

```typescript
// ui-electron/shared/types/settings.ts

export type GPUMode = 'auto' | 'force_gpu' | 'force_cpu';
export type ComputeType = 'int8' | 'float16' | 'float32';
export type ModelSize = 'auto' | 'tiny' | 'base' | 'small' | 'medium' | 'large-v3';
export type LanguageMode = 'auto' | 'force_hindi' | 'force_english';
export type HotkeyMode = 'push_to_talk' | 'toggle' | 'instant';
export type FloatingPosition = 'bottom-center' | 'bottom-left' | 'bottom-right' | 'custom';

export interface PerformanceSettings {
  gpuMode: GPUMode;
  computeType: ComputeType;
  modelOverride: ModelSize;
  device: 'cuda' | 'cpu';
  workers: number;
}

export interface AudioPipelineSettings {
  chunkDuration: number;      // 0.1s to 5.0s
  overlapRatio: number;       // 0.0 to 0.5
  bufferSize: number;         // 1s to 10s
  vadEnabled: boolean;
  vadThreshold: number;       // -60 to -20 dB
  vadMinSilence: number;      // 100 to 1000ms
  vadSpeechPad: number;       // 0 to 500ms
}

export interface QualitySettings {
  confidenceThreshold: number;     // 0.5 to 0.95
  enableFillerFilter: boolean;
  enableHallucinationFilter: boolean;
  minSegmentLength: number;        // characters
  maxSegmentGap: number;           // seconds for merging
}

export interface HotkeySettings {
  hotkeyEnabled: boolean;
  hotkeyCombo: string;             // e.g., "Ctrl+Win", "Alt+Space"
  hotkeyMode: HotkeyMode;
  floatingUI: boolean;
  floatingPosition: FloatingPosition;
  floatingOpacity: number;         // 0.3 to 1.0
  minimizeToTray: boolean;
}

export interface ExperimentalSettings {
  beamSize: number;           // 1 to 5
  bestOf: number;             // 1 to 5
  temperature: number;        // 0.0 to 1.0
  patience: number;           // 0.0 to 2.0
  lengthPenalty: number;      // 0.0 to 2.0
  suppressTokens: string[];   // e.g., ["-1"]
  conditionOnPrevious: boolean;
  initialPrompt: string;
  languageDetection: LanguageMode;
}

export interface AdvancedSettings {
  performance: PerformanceSettings;
  audio: AudioPipelineSettings;
  quality: QualitySettings;
  hotkey: HotkeySettings;
  experimental: ExperimentalSettings;
}
```

### 2.2 Preset System

```typescript
// ui-electron/shared/config/presets.ts

import { AdvancedSettings } from '../types/settings';

export interface Preset {
  name: string;
  description: string;
  icon: string;
  settings: Partial<AdvancedSettings>;
}

export const PRESETS: Record<string, Preset> = {
  maximum_quality: {
    name: 'Maximum Quality',
    description: 'Best accuracy, higher latency. Use for important recordings.',
    icon: 'award',
    settings: {
      performance: {
        gpuMode: 'auto',
        computeType: 'float16',
        modelOverride: 'large-v3',
        device: 'cuda',
        workers: 1
      },
      audio: {
        chunkDuration: 1.0,
        overlapRatio: 0.2,
        bufferSize: 5.0,
        vadEnabled: true,
        vadThreshold: -40.0,
        vadMinSilence: 300,
        vadSpeechPad: 100
      },
      quality: {
        confidenceThreshold: 0.75,
        enableFillerFilter: true,
        enableHallucinationFilter: true,
        minSegmentLength: 3,
        maxSegmentGap: 2.0
      },
      experimental: {
        beamSize: 5,
        bestOf: 5,
        temperature: 0.0,
        patience: 1.0,
        lengthPenalty: 1.0,
        conditionOnPrevious: true
      }
    }
  },
  
  balanced: {
    name: 'Balanced',
    description: 'Good accuracy with reasonable latency. Recommended default.',
    icon: 'scale',
    settings: {
      performance: {
        gpuMode: 'auto',
        computeType: 'float16',
        modelOverride: 'medium',
        device: 'cuda',
        workers: 1
      },
      audio: {
        chunkDuration: 0.8,
        overlapRatio: 0.1,
        bufferSize: 3.0,
        vadEnabled: true,
        vadThreshold: -40.0,
        vadMinSilence: 200,
        vadSpeechPad: 50
      },
      quality: {
        confidenceThreshold: 0.70,
        enableFillerFilter: true,
        enableHallucinationFilter: false,
        minSegmentLength: 2,
        maxSegmentGap: 3.0
      },
      experimental: {
        beamSize: 5,
        bestOf: 5,
        temperature: 0.0,
        patience: 1.0,
        lengthPenalty: 1.0,
        conditionOnPrevious: true
      }
    }
  },
  
  maximum_speed: {
    name: 'Maximum Speed',
    description: 'Lowest latency, acceptable quality. Good for live dictation.',
    icon: 'zap',
    settings: {
      performance: {
        gpuMode: 'auto',
        computeType: 'int8',
        modelOverride: 'tiny',
        device: 'cuda',
        workers: 1
      },
      audio: {
        chunkDuration: 0.2,
        overlapRatio: 0.0,
        bufferSize: 1.0,
        vadEnabled: true,
        vadThreshold: -35.0,
        vadMinSilence: 100,
        vadSpeechPad: 0
      },
      quality: {
        confidenceThreshold: 0.60,
        enableFillerFilter: false,
        enableHallucinationFilter: false,
        minSegmentLength: 1,
        maxSegmentGap: 5.0
      },
      experimental: {
        beamSize: 1,
        bestOf: 1,
        temperature: 0.0,
        patience: 0.0,
        lengthPenalty: 1.0,
        conditionOnPrevious: false
      }
    }
  },
  
  low_memory: {
    name: 'Low Memory',
    description: 'Optimized for systems with limited RAM or VRAM.',
    icon: 'memory',
    settings: {
      performance: {
        gpuMode: 'force_cpu',
        computeType: 'int8',
        modelOverride: 'small',
        device: 'cpu',
        workers: 2
      },
      audio: {
        chunkDuration: 1.5,
        overlapRatio: 0.0,
        bufferSize: 3.0,
        vadEnabled: true,
        vadThreshold: -40.0,
        vadMinSilence: 300,
        vadSpeechPad: 50
      },
      quality: {
        confidenceThreshold: 0.65,
        enableFillerFilter: true,
        enableHallucinationFilter: false,
        minSegmentLength: 2,
        maxSegmentGap: 3.0
      },
      experimental: {
        beamSize: 1,
        bestOf: 1,
        temperature: 0.0,
        patience: 0.0,
        lengthPenalty: 1.0,
        conditionOnPrevious: false
      }
    }
  },
  
  hotkey_mode: {
    name: 'Hotkey Mode',
    description: 'Optimized for push-to-talk usage with instant response.',
    icon: 'mic',
    settings: {
      performance: {
        gpuMode: 'auto',
        computeType: 'int8',
        modelOverride: 'base',
        device: 'cuda',
        workers: 1
      },
      audio: {
        chunkDuration: 0.3,
        overlapRatio: 0.0,
        bufferSize: 1.0,
        vadEnabled: true,
        vadThreshold: -40.0,
        vadMinSilence: 150,
        vadSpeechPad: 0
      },
      quality: {
        confidenceThreshold: 0.60,
        enableFillerFilter: true,
        enableHallucinationFilter: false,
        minSegmentLength: 1,
        maxSegmentGap: 2.0
      },
      experimental: {
        beamSize: 1,
        bestOf: 1,
        temperature: 0.0,
        patience: 0.0,
        lengthPenalty: 1.0,
        conditionOnPrevious: false
      }
    }
  }
};

export function applyPreset(
  baseSettings: AdvancedSettings,
  presetKey: string
): AdvancedSettings {
  const preset = PRESETS[presetKey];
  if (!preset) return baseSettings;
  
  return {
    ...baseSettings,
    ...preset.settings,
    performance: { ...baseSettings.performance, ...preset.settings.performance },
    audio: { ...baseSettings.audio, ...preset.settings.audio },
    quality: { ...baseSettings.quality, ...preset.settings.quality },
    experimental: { ...baseSettings.experimental, ...preset.settings.experimental }
  };
}
```

### 2.3 React Components Structure

```typescript
// ui-electron/frontend/src/components/settings/

// AdvancedSettingsPanel.tsx - Main container
// ├── SettingsSection.tsx - Collapsible section wrapper
// ├── PerformanceSettings.tsx
// │   ├── GPUModeSelector
// │   ├── ComputeTypeSelector
// │   └── ModelOverrideSelector
// ├── AudioPipelineSettings.tsx
// │   ├── ChunkDurationSlider
// │   ├── VADThresholdSlider
// │   └── BufferSizeSelector
// ├── QualitySettings.tsx
// │   ├── ConfidenceThresholdSlider
// │   └── FilterToggles
// ├── HotkeySettings.tsx
// │   ├── HotkeyRecorder
// │   ├── ModeSelector
// │   └── FloatingUIPreview
// └── ExperimentalSettings.tsx
//     ├── BeamSizeControl
//     ├── TemperatureSlider
//     └── LanguageSelector
```

---

## 3. Global Hotkey System

### 3.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER ACTION                             │
│                      (Press Global Hotkey)                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ELECTRON MAIN PROCESS                        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ GlobalShortcut│───▶│  IPC Bridge  │───▶│   Backend    │      │
│  │   (iohook)   │    │   (ipcMain)  │    │  (Python)    │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│           │                                        │            │
│           ▼                                        ▼            │
│  ┌─────────────────┐                    ┌──────────────┐       │
│  │ Floating Window │◀───────────────────│   Audio      │       │
│  │   (BrowserWin)  │    (transcription) │   Capture    │       │
│  └─────────────────┘                    └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     OUTPUT DELIVERY                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  TypeText    │───▶│ Active Window│    │ Copy to      │      │
│  │  (robotjs)   │    │   (focus)    │    │ Clipboard    │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Electron Main Process

```typescript
// ui-electron/main/hotkey/GlobalHotkeyManager.ts

import { globalShortcut, BrowserWindow, ipcMain } from 'electron';
import { EventEmitter } from 'events';

export interface HotkeyCombo {
  key: string;
  ctrl?: boolean;
  alt?: boolean;
  shift?: boolean;
  meta?: boolean;  // Windows key / Command
}

export class GlobalHotkeyManager extends EventEmitter {
  private registeredCombo: string | null = null;
  private isRecording: boolean = false;
  private floatingWindow: BrowserWindow | null = null;
  
  constructor() {
    super();
    this.setupIPC();
  }
  
  private setupIPC(): void {
    ipcMain.handle('hotkey:register', (_, combo: string) => {
      return this.registerHotkey(combo);
    });
    
    ipcMain.handle('hotkey:unregister', () => {
      return this.unregisterHotkey();
    });
    
    ipcMain.handle('hotkey:start-recording', () => {
      this.startRecording();
    });
    
    ipcMain.handle('hotkey:stop-recording', () => {
      this.stopRecording();
    });
    
    // From renderer: transcription result ready
    ipcMain.on('hotkey:result-ready', (_, text: string) => {
      this.injectTextToActiveWindow(text);
    });
  }
  
  registerHotkey(combo: string): boolean {
    // Unregister existing
    if (this.registeredCombo) {
      globalShortcut.unregister(this.registeredCombo);
    }
    
    // Validate combo format
    if (!this.isValidCombo(combo)) {
      return false;
    }
    
    // Register new
    const success = globalShortcut.register(combo, () => {
      this.onHotkeyPressed();
    });
    
    if (success) {
      this.registeredCombo = combo;
      console.log(`[Hotkey] Registered: ${combo}`);
    }
    
    return success;
  }
  
  unregisterHotkey(): void {
    if (this.registeredCombo) {
      globalShortcut.unregister(this.registeredCombo);
      this.registeredCombo = null;
      console.log('[Hotkey] Unregistered');
    }
  }
  
  private onHotkeyPressed(): void {
    this.emit('hotkey:pressed');
    this.showFloatingWindow();
    
    // Notify backend to start capture
    this.notifyBackend('hotkey:start-capture');
  }
  
  private onHotkeyReleased(): void {
    this.emit('hotkey:released');
    
    // Notify backend to stop capture and transcribe
    this.notifyBackend('hotkey:stop-capture');
  }
  
  private showFloatingWindow(): void {
    if (!this.floatingWindow) {
      this.createFloatingWindow();
    }
    
    this.floatingWindow?.show();
    this.floatingWindow?.focus();
    
    // Position at bottom-center of primary display
    const { screen } = require('electron');
    const primary = screen.getPrimaryDisplay();
    const { width, height } = this.floatingWindow?.getBounds() || { width: 400, height: 120 };
    
    this.floatingWindow?.setPosition(
      Math.round(primary.bounds.width / 2 - width / 2),
      Math.round(primary.bounds.height - height - 50)
    );
  }
  
  private createFloatingWindow(): void {
    const { BrowserWindow } = require('electron');
    
    this.floatingWindow = new BrowserWindow({
      width: 400,
      height: 120,
      show: false,
      alwaysOnTop: true,
      skipTaskbar: true,
      frame: false,
      transparent: true,
      resizable: false,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: require('path').join(__dirname, '../preload/floating.js')
      }
    });
    
    this.floatingWindow.loadFile('floating.html');
    
    // Hide on blur
    this.floatingWindow.on('blur', () => {
      // Don't hide immediately to allow click-through
    });
  }
  
  private async injectTextToActiveWindow(text: string): void {
    try {
      // Hide floating window first
      this.floatingWindow?.hide();
      
      // Use accessibility API or robotjs to type text
      const robot = require('robotjs');
      
      // Small delay to ensure focus is on target window
      await new Promise(r => setTimeout(r, 50));
      
      // Type the text
      robot.typeString(text);
      
      console.log(`[Hotkey] Injected text: ${text.substring(0, 50)}...`);
    } catch (error) {
      console.error('[Hotkey] Failed to inject text:', error);
      // Fallback: copy to clipboard
      const { clipboard } = require('electron');
      clipboard.writeText(text);
    }
  }
  
  private isValidCombo(combo: string): boolean {
    // Validate: must have at least one modifier + key
    const validModifiers = ['Control', 'Alt', 'Shift', 'Super'];
    const parts = combo.split('+').map(p => p.trim());
    
    const hasModifier = parts.some(p => 
      validModifiers.some(m => p.toLowerCase().includes(m.toLowerCase()))
    );
    
    const hasKey = parts.some(p => 
      !validModifiers.some(m => p.toLowerCase().includes(m.toLowerCase()))
    );
    
    return hasModifier && hasKey;
  }
  
  destroy(): void {
    this.unregisterHotkey();
    this.floatingWindow?.destroy();
  }
}
```

### 3.3 Floating UI Component

```typescript
// ui-electron/floating/FloatingTranscriptionWindow.tsx

import React, { useState, useEffect, useCallback } from 'react';
import { ipcRenderer } from 'electron';
import { Mic, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';

interface FloatingUIState {
  status: 'idle' | 'listening' | 'processing' | 'error';
  transcript: string;
  isPartial: boolean;
  audioLevel: number;
}

export const FloatingTranscriptionWindow: React.FC = () => {
  const [state, setState] = useState<FloatingUIState>({
    status: 'idle',
    transcript: '',
    isPartial: false,
    audioLevel: 0
  });
  
  useEffect(() => {
    // Listen for state updates from main process
    ipcRenderer.on('floating:status', (_, status: FloatingUIState['status']) => {
      setState(prev => ({ ...prev, status }));
    });
    
    ipcRenderer.on('floating:transcript', (_, { text, isPartial }) => {
      setState(prev => ({ 
        ...prev, 
        transcript: text, 
        isPartial 
      }));
    });
    
    ipcRenderer.on('floating:audio-level', (_, level: number) => {
      setState(prev => ({ ...prev, audioLevel: level }));
    });
    
    ipcRenderer.on('floating:complete', (_, text: string) => {
      // Send result back to main for injection
      ipcRenderer.send('hotkey:result-ready', text);
    });
    
    return () => {
      ipcRenderer.removeAllListeners('floating:status');
      ipcRenderer.removeAllListeners('floating:transcript');
      ipcRenderer.removeAllListeners('floating:audio-level');
      ipcRenderer.removeAllListeners('floating:complete');
    };
  }, []);
  
  const getStatusIcon = () => {
    switch (state.status) {
      case 'listening':
        return <Mic className="w-6 h-6 text-red-500 animate-pulse" />;
      case 'processing':
        return <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />;
      case 'error':
        return <AlertCircle className="w-6 h-6 text-red-500" />;
      default:
        return <Mic className="w-6 h-6 text-gray-400" />;
    }
  };
  
  return (
    <div className="floating-window bg-gray-900/95 rounded-xl p-4 shadow-2xl border border-gray-700">
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        {getStatusIcon()}
        <span className="text-sm font-medium text-gray-200">
          {state.status === 'listening' && 'Listening...'}
          {state.status === 'processing' && 'Processing...'}
          {state.status === 'error' && 'Error'}
          {state.status === 'idle' && 'Ready'}
        </span>
        
        {/* Audio Visualizer */}
        {state.status === 'listening' && (
          <AudioVisualizer level={state.audioLevel} />
        )}
      </div>
      
      {/* Transcript Preview */}
      <div className="transcript-preview min-h-[40px] text-white text-lg">
        {state.transcript || (
          <span className="text-gray-500 italic">
            {state.status === 'listening' ? 'Speak now...' : 'Press hotkey to start'}
          </span>
        )}
        {state.isPartial && (
          <span className="animate-pulse">...</span>
        )}
      </div>
      
      {/* Quick Settings Bar */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-700">
        <LanguageIndicator />
        <ModelIndicator />
        <button 
          onClick={() => ipcRenderer.send('floating:cancel')}
          className="ml-auto text-xs text-gray-500 hover:text-gray-300"
        >
          Cancel (Esc)
        </button>
      </div>
    </div>
  );
};

// Audio Visualizer Component
const AudioVisualizer: React.FC<{ level: number }> = ({ level }) => {
  const bars = 5;
  
  return (
    <div className="flex items-end gap-1 h-6">
      {Array.from({ length: bars }).map((_, i) => {
        const threshold = (i + 1) * (100 / bars);
        const active = level >= threshold;
        const height = active ? `${20 + i * 8}px` : '4px';
        
        return (
          <div
            key={i}
            className={`w-1 rounded-t transition-all duration-75 ${
              active ? 'bg-green-400' : 'bg-gray-600'
            }`}
            style={{ height }}
          />
        );
      })}
    </div>
  );
};
```

### 3.4 Push-to-Talk Controller

```typescript
// ui-electron/floating/PushToTalkController.ts

import { ipcRenderer } from 'electron';

export enum HotkeyMode {
  PUSH_TO_TALK = 'push_to_talk',
  TOGGLE = 'toggle',
  INSTANT = 'instant'
}

export class PushToTalkController {
  private mode: HotkeyMode = HotkeyMode.PUSH_TO_TALK;
  private isRecording: boolean = false;
  private silenceTimer: NodeJS.Timeout | null = null;
  private readonly SILENCE_THRESHOLD = 1500; // ms
  
  constructor(mode: HotkeyMode) {
    this.mode = mode;
    this.setupListeners();
  }
  
  private setupListeners(): void {
    ipcRenderer.on('hotkey:pressed', () => this.onHotkeyPressed());
    ipcRenderer.on('hotkey:released', () => this.onHotkeyReleased());
    ipcRenderer.on('audio:silence-detected', () => this.onSilenceDetected());
  }
  
  private onHotkeyPressed(): void {
    switch (this.mode) {
      case HotkeyMode.PUSH_TO_TALK:
        this.startRecording();
        break;
        
      case HotkeyMode.TOGGLE:
        if (this.isRecording) {
          this.stopRecording();
        } else {
          this.startRecording();
        }
        break;
        
      case HotkeyMode.INSTANT:
        this.startRecording();
        this.startSilenceDetection();
        break;
    }
  }
  
  private onHotkeyReleased(): void {
    if (this.mode === HotkeyMode.PUSH_TO_TALK) {
      this.stopRecording();
    }
    // TOGGLE and INSTANT handle release differently
  }
  
  private startRecording(): void {
    this.isRecording = true;
    
    // Update UI
    ipcRenderer.send('floating:status', 'listening');
    
    // Start backend capture
    ipcRenderer.send('backend:start-stream');
    
    console.log('[PushToTalk] Recording started');
  }
  
  private stopRecording(): void {
    if (!this.isRecording) return;
    
    this.isRecording = false;
    this.clearSilenceTimer();
    
    // Update UI
    ipcRenderer.send('floating:status', 'processing');
    
    // Stop backend capture and get result
    ipcRenderer.send('backend:stop-stream');
    
    console.log('[PushToTalk] Recording stopped');
  }
  
  private startSilenceDetection(): void {
    this.clearSilenceTimer();
    this.silenceTimer = setTimeout(() => {
      if (this.isRecording) {
        console.log('[PushToTalk] Auto-stopped on silence');
        this.stopRecording();
      }
    }, this.SILENCE_THRESHOLD);
  }
  
  private onSilenceDetected(): void {
    if (this.mode === HotkeyMode.INSTANT && this.isRecording) {
      this.startSilenceDetection();
    }
  }
  
  private clearSilenceTimer(): void {
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
  }
  
  setMode(mode: HotkeyMode): void {
    this.mode = mode;
    // If switching modes while recording, stop first
    if (this.isRecording) {
      this.stopRecording();
    }
  }
  
  destroy(): void {
    this.clearSilenceTimer();
    ipcRenderer.removeAllListeners('hotkey:pressed');
    ipcRenderer.removeAllListeners('hotkey:released');
    ipcRenderer.removeAllListeners('audio:silence-detected');
  }
}
```

---

## 4. Performance Optimizations

### 4.1 Model Preloading & Cache

```python
# app/stt/model_cache.py

import torch
from pathlib import Path
from typing import Optional, Dict
from faster_whisper import WhisperModel
import threading
import time

class ModelCache:
    """Keeps models in GPU memory for instant hotkey response."""
    
    def __init__(self, cache_dir: Path = Path("models")):
        self.cache_dir = cache_dir
        self._cache: Dict[str, WhisperModel] = {}
        self._lock = threading.RLock()
        self._last_access: Dict[str, float] = {}
        self._preload_thread: Optional[threading.Thread] = None
        self._standby_mode = False
    
    def preload(self, model_size: str, device: str = "cuda", 
                compute_type: str = "int8") -> bool:
        """Preload model into GPU memory."""
        cache_key = f"{model_size}_{device}_{compute_type}"
        
        with self._lock:
            if cache_key in self._cache:
                self._last_access[cache_key] = time.time()
                return True
        
        try:
            print(f"[ModelCache] Preloading {model_size} on {device}...")
            model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                download_root=str(self.cache_dir),
                cpu_threads=4 if device == "cpu" else 1
            )
            
            with self._lock:
                self._cache[cache_key] = model
                self._last_access[cache_key] = time.time()
            
            print(f"[ModelCache] Preloaded {model_size}")
            return True
            
        except Exception as e:
            print(f"[ModelCache] Failed to preload {model_size}: {e}")
            return False
    
    def preload_for_hotkey(self, model_size: str = "base") -> None:
        """Background preload for hotkey mode."""
        def _preload():
            self.preload(model_size, device="cuda", compute_type="int8")
            self._standby_mode = True
        
        self._preload_thread = threading.Thread(target=_preload, daemon=True)
        self._preload_thread.start()
    
    def get_model(self, model_size: str, device: str = "cuda",
                  compute_type: str = "int8") -> WhisperModel:
        """Get cached model or load if not cached."""
        cache_key = f"{model_size}_{device}_{compute_type}"
        
        with self._lock:
            if cache_key in self._cache:
                self._last_access[cache_key] = time.time()
                return self._cache[cache_key]
        
        # Not cached, load now
        self.preload(model_size, device, compute_type)
        
        with self._lock:
            return self._cache[cache_key]
    
    def quick_transcribe(self, audio_path: Path, 
                         model_size: str = "base") -> str:
        """Fast transcription for hotkey mode. Bypasses queue."""
        model = self.get_model(model_size, device="cuda", compute_type="int8")
        
        segments, _ = model.transcribe(
            str(audio_path),
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            no_speech_threshold=0.6
        )
        
        return " ".join([s.text for s in segments]).strip()
    
    def evict_lru(self, max_cache_size: int = 2) -> None:
        """Evict least recently used models if cache exceeds size."""
        with self._lock:
            while len(self._cache) > max_cache_size:
                # Find LRU
                lru_key = min(self._last_access, key=self._last_access.get)
                
                print(f"[ModelCache] Evicting {lru_key}")
                del self._cache[lru_key]
                del self._last_access[lru_key]
                
                # Force garbage collection
                torch.cuda.empty_cache()
    
    def clear(self) -> None:
        """Clear all cached models."""
        with self._lock:
            self._cache.clear()
            self._last_access.clear()
            torch.cuda.empty_cache()
```

### 4.2 Streaming Transcriber

```python
# app/stt/streaming_transcriber.py

import numpy as np
import torch
from typing import Callable, Optional
from dataclasses import dataclass
import threading
import queue
import time

from .model_cache import ModelCache
from ..audio.capture import AudioCapture

@dataclass
class TranscriptionSegment:
    text: str
    is_partial: bool
    confidence: float
    start_time: float
    end_time: float


class StreamingTranscriber:
    """Real-time transcription for hotkey mode."""
    
    def __init__(self, model_cache: ModelCache, 
                 model_size: str = "base"):
        self.model_cache = model_cache
        self.model_size = model_size
        self.capture: Optional[AudioCapture] = None
        self._stream_thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=100)
        self._is_streaming = False
        self._callbacks: list[Callable[[TranscriptionSegment], None]] = []
        
        # Streaming settings
        self.chunk_duration = 0.3  # seconds
        self.sample_rate = 16000
        self.chunk_samples = int(self.sample_rate * self.chunk_duration)
    
    def add_callback(self, callback: Callable[[TranscriptionSegment], None]) -> None:
        self._callbacks.append(callback)
    
    def start_stream(self, device_id: Optional[int] = None) -> None:
        """Start real-time audio stream and transcription."""
        if self._is_streaming:
            return
        
        self._is_streaming = True
        
        # Initialize audio capture
        self.capture = AudioCapture(
            sample_rate=self.sample_rate,
            chunk_duration=self.chunk_duration,
            device_id=device_id
        )
        
        # Start capture thread
        self._stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._stream_thread.start()
        
        print("[StreamingTranscriber] Stream started")
    
    def stop_stream(self) -> str:
        """Stop streaming and return final transcription."""
        self._is_streaming = False
        
        # Wait for thread
        if self._stream_thread:
            self._stream_thread.join(timeout=2.0)
        
        # Drain remaining audio
        remaining = []
        while not self._audio_queue.empty():
            try:
                remaining.append(self._audio_queue.get_nowait())
            except queue.Empty:
                break
        
        # Final transcription
        if remaining:
            final_audio = np.concatenate(remaining)
            return self._transcribe_chunk(final_audio, is_final=True)
        
        return ""
    
    def _stream_loop(self) -> None:
        """Main streaming loop."""
        buffer = np.array([], dtype=np.float32)
        
        while self._is_streaming:
            try:
                # Get audio chunk (non-blocking)
                chunk = self.capture.read_chunk(timeout=0.1)
                
                if chunk is None:
                    continue
                
                buffer = np.concatenate([buffer, chunk])
                
                # Process when we have enough samples
                if len(buffer) >= self.chunk_samples:
                    process_buffer = buffer[:self.chunk_samples]
                    buffer = buffer[self.chunk_samples:]
                    
                    # Transcribe in background
                    threading.Thread(
                        target=self._process_and_emit,
                        args=(process_buffer,),
                        daemon=True
                    ).start()
                    
            except Exception as e:
                print(f"[StreamingTranscriber] Stream error: {e}")
                break
    
    def _process_and_emit(self, audio: np.ndarray) -> None:
        """Process audio chunk and emit partial result."""
        text = self._transcribe_chunk(audio, is_final=False)
        
        if text:
            segment = TranscriptionSegment(
                text=text,
                is_partial=True,
                confidence=0.8,  # Estimated
                start_time=time.time() - self.chunk_duration,
                end_time=time.time()
            )
            
            for callback in self._callbacks:
                callback(segment)
    
    def _transcribe_chunk(self, audio: np.ndarray, 
                          is_final: bool = False) -> str:
        """Transcribe single audio chunk."""
        model = self.model_cache.get_model(self.model_size)
        
        # Convert to format expected by faster-whisper
        # This is simplified - actual implementation needs proper preprocessing
        
        segments, info = model.transcribe(
            audio,
            beam_size=1 if not is_final else 5,
            best_of=1 if not is_final else 5,
            temperature=0.0,
            condition_on_previous_text=not is_final,
            compression_ratio_threshold=2.4,
            no_speech_threshold=0.6,
            language="hi"  # Or auto-detect
        )
        
        texts = [s.text for s in segments]
        return " ".join(texts).strip()
```

---

## 5. Implementation Roadmap

### Phase 1: Auto-Optimization (Week 1-2)

**Deliverables:**
- [ ] `SystemProfiler` implementation with GPU/CPU/storage detection
- [ ] `AutoOptimizer` config generation with VRAM-based rules
- [ ] Settings migration system (`SettingsMigration`)
- [ ] IPC endpoints for profile retrieval
- [ ] UI for "Recommended Settings" banner

**Verification:**
```powershell
# Test profiler
python -c "from app.optimizer.profiler import SystemProfiler; p = SystemProfiler(); print(p.get_full_profile())"

# Test optimizer
python -c "from app.optimizer.auto_optimizer import AutoOptimizer; ..."
```

### Phase 2: Advanced Settings Panel (Week 2-3)

**Deliverables:**
- [ ] TypeScript interfaces for all settings categories
- [ ] React component hierarchy implementation
- [ ] Preset system with 5 presets (maximum_quality, balanced, maximum_speed, low_memory, hotkey_mode)
- [ ] Real-time settings validation
- [ ] Settings import/export (JSON)
- [ ] A/B comparison UI for presets

**Components:**
| Component | LOC Estimate | Complexity |
|-----------|--------------|------------|
| AdvancedSettingsPanel | 150 | Medium |
| PerformanceSettings | 200 | Medium |
| AudioPipelineSettings | 250 | High |
| QualitySettings | 150 | Low |
| HotkeySettings | 300 | High |
| ExperimentalSettings | 200 | Medium |
| PresetSelector | 100 | Low |

### Phase 3: Global Hotkey (Week 3-4)

**Deliverables:**
- [ ] `GlobalHotkeyManager` in Electron main process
- [ ] Floating window (`FloatingTranscriptionWindow`)
- [ ] Audio visualizer component
- [ ] `PushToTalkController` with 3 modes
- [ ] System tray integration
- [ ] Text injection via robotjs

**Windows-Specific:**
- Global shortcuts use `globalShortcut` API
- Text injection uses `robotjs` with accessibility permissions
- Floating window always-on-top via `alwaysOnTop: true`

**Testing Matrix:**
| OS Version | Hotkey Registration | Text Injection | Floating UI |
|------------|---------------------|----------------|-------------|
| Windows 10 | Required | Required | Required |
| Windows 11 | Required | Required | Required |

### Phase 4: Integration (Week 4-5)

**Deliverables:**
- [ ] Hotkey → Backend connection via IPC
- [ ] `StreamingTranscriber` integration
- [ ] `ModelCache` preloading on app start
- [ ] Audio pipeline optimization for < 500ms first result
- [ ] End-to-end latency testing

**Performance Targets:**
| Metric | Target | Measurement |
|--------|--------|-------------|
| Hotkey response (UI) | < 50ms | Time from keypress to window visible |
| First partial result | < 500ms | Time to first "..." shown |
| Final transcription | < 2 seconds | Short phrase (5 words) |
| GPU inference/chunk | < 300ms | `tiny` model chunk |

---

## 6. Technical Specifications

### 6.1 Minimum Requirements Detection

```python
# app/optimizer/requirements.py

from dataclasses import dataclass

@dataclass(frozen=True)
class MinimumSpecs:
    CPU_CORES: int = 4
    RAM_GB: int = 8
    GPU_VRAM_GB: float = 4.0  # Optional
    FREE_STORAGE_GB: float = 10.0
    WINDOWS_VERSION: int = 10  # Windows 10 or higher

MINIMUM_SPECS = MinimumSpecs()


def check_minimum_requirements(profile: SystemProfile) -> tuple[bool, list[str]]:
    """Check if system meets minimum requirements."""
    warnings = []
    
    if profile.cpu.cores < MINIMUM_SPECS.CPU_CORES:
        warnings.append(
            f"CPU: {profile.cpu.cores} cores < {MINIMUM_SPECS.CPU_CORES} required"
        )
    
    if profile.cpu.ram_gb < MINIMUM_SPECS.RAM_GB:
        warnings.append(
            f"RAM: {profile.cpu.ram_gb:.1f}GB < {MINIMUM_SPECS.RAM_GB}GB required"
        )
    
    if profile.storage.free_gb < MINIMUM_SPECS.FREE_STORAGE_GB:
        warnings.append(
            f"Storage: {profile.storage.free_gb:.1f}GB free < "
            f"{MINIMUM_SPECS.FREE_STORAGE_GB}GB required"
        )
    
    if profile.gpu is None:
        warnings.append(
            "No GPU detected. CPU-only mode will be slower."
        )
    elif profile.gpu.vram_gb < MINIMUM_SPECS.GPU_VRAM_GB:
        warnings.append(
            f"GPU VRAM: {profile.gpu.vram_gb:.1f}GB < "
            f"{MINIMUM_SPECS.GPU_VRAM_GB}GB recommended"
        )
    
    return len(warnings) == 0, warnings
```

### 6.2 Performance Targets

| Component | Target | Max Acceptable | Measurement Method |
|-----------|--------|----------------|-------------------|
| **Hotkey Response** | < 50ms | 100ms | `console.time()` in main process |
| **First Partial** | < 500ms | 1s | UI timestamp vs hotkey timestamp |
| **Final Result** | < 2s | 5s | 5-word phrase end-to-end |
| **GPU Inference** | < 300ms | 500ms | Per-chunk timing logs |
| **Memory Pressure** | < 80% | 90% | `psutil.virtual_memory()` |
| **GPU Memory** | < 80% | 95% | `torch.cuda.memory_allocated()` |

### 6.3 Error Handling

| Scenario | Handling |
|----------|----------|
| Hotkey registration fails | Show error banner, suggest different combo |
| GPU OOM during hotkey | Fall back to CPU, show warning |
| Text injection fails | Copy to clipboard, notify user |
| Audio capture fails | Show floating error, allow retry |
| Model not preloaded | Load on-demand with progress indicator |

### 6.4 Security Considerations

- Global hotkeys require app to be running (no background service)
- Text injection requires accessibility permissions on Windows
- No keystroke logging outside of transcription hotkey
- Audio data never leaves local machine
- Floating window is transparent but not click-through (security)

---

## Appendix A: File Structure

```
transcripta/
├── app/
│   ├── optimizer/
│   │   ├── __init__.py
│   │   ├── profiler.py          # SystemProfiler
│   │   ├── auto_optimizer.py    # AutoOptimizer
│   │   ├── migration.py         # SettingsMigration
│   │   └── requirements.py      # Minimum specs
│   ├── stt/
│   │   ├── model_cache.py       # ModelCache
│   │   └── streaming_transcriber.py
│   └── api/
│       └── routes/
│           └── optimizer.py     # FastAPI endpoints
├── ui-electron/
│   ├── main/
│   │   ├── hotkey/
│   │   │   └── GlobalHotkeyManager.ts
│   │   └── floating/
│   │       └── createFloatingWindow.ts
│   ├── floating/                 # Floating UI renderer
│   │   ├── FloatingTranscriptionWindow.tsx
│   │   ├── PushToTalkController.ts
│   │   └── AudioVisualizer.tsx
│   └── frontend/
│       └── src/
│           └── components/
│               └── settings/
│                   ├── AdvancedSettingsPanel.tsx
│                   ├── PerformanceSettings.tsx
│                   ├── AudioPipelineSettings.tsx
│                   ├── QualitySettings.tsx
│                   ├── HotkeySettings.tsx
│                   ├── ExperimentalSettings.tsx
│                   └── PresetSelector.tsx
└── docs/
    └── ARCHITECTURE_PLAN.md      # This document
```

## Appendix B: Dependencies

```txt
# Python additions
psutil>=5.9.0
py-cpuinfo>=9.0.0
WMI>=1.5.1; platform_system=="Windows"

# Node.js additions
# (already included)
# - electron
# - robotjs (for text injection)
```

## Appendix C: Configuration Schema

```json
{
  "version": "2.0",
  "auto_optimized": true,
  "hardware_profile": {
    "gpu": {
      "name": "NVIDIA GeForce RTX 3060",
      "vram_gb": 12.0,
      "compute_capability": [8, 6]
    },
    "cpu": {
      "cores": 8,
      "ram_gb": 16.0,
      "has_avx2": true
    }
  },
  "settings": {
    "performance": {
      "gpuMode": "auto",
      "computeType": "float16",
      "modelOverride": "large-v3",
      "workers": 1
    },
    "audio": {
      "chunkDuration": 1.0,
      "vadThreshold": -40.0
    },
    "hotkey": {
      "enabled": true,
      "combo": "Ctrl+Win",
      "mode": "push_to_talk",
      "floatingUI": true
    }
  },
  "presets": {
    "last_used": "balanced",
    "custom": []
  }
}
```
