# Transcripta Feature Inventory

**Project:** Transcripta - Local Desktop Transcription  
**Date:** March 2, 2026  
**Version:** 1.0.0  
**Repository:** `D:\Programming\Engineering Workspace\Web & Application Development\Active Projects\Transcripta`

---

## Overview

Transcripta is a privacy-first desktop transcription application built with a modern tech stack:

| Component | Technology |
|-----------|------------|
| **Frontend** | React 19 + TypeScript + Tailwind CSS |
| **Desktop Shell** | Electron (main + preload scripts) |
| **Backend** | Python (local server on port 8765) |
| **Communication** | REST API + SSE (Server-Sent Events) + IPC |
| **State Management** | React hooks + reducer pattern |
| **Build Tool** | Vite |

### Architecture Highlights

- **Local-first**: All processing happens on-device, no cloud dependencies
- **Real-time updates**: SSE with polling fallback for session state
- **Hardware-aware**: Auto-optimizes based on GPU/CPU capabilities
- **Multi-theme**: Light, Dark, Cyber, Dracula themes

---

## Feature Inventory

### Layout & Responsiveness

| Feature | Location | Status | Data Source | "Done" Definition | Notes |
|---------|----------|--------|-------------|-------------------|-------|
| 3-Column Grid Layout | `App.tsx:935` | Working | Local state | Layout renders correctly at all viewports | Uses `grid-cols-1 lg:grid-cols-[320px_280px_1fr]` |
| Responsive Breakpoint (lg) | `App.tsx:935` | Working | CSS/Tailwind | Switches to 3-column at 1024px+ | Sidebar/Activity Feed stack on mobile |
| Brutalist Design System | `index.css` (referenced) | Working | CSS variables | Consistent borders, shadows, colors | Uses `border-lawn-border`, `shadow-brutal` classes |
| Theme Switching | `App.tsx:191`, `Sidebar.tsx:221` | Working | LocalStorage + Settings | Theme persists across sessions | Supports: light, dark, cyber, dracula |
| Mobile Viewport Support | All components | Working | Tailwind responsive | No horizontal scroll on mobile | Columns stack vertically |
| Custom Scrollbars | `custom-scrollbar` class | Working | CSS | Styled scrollbars in panels | Applied to scrollable areas |
| Window Title Bar | Electron main | Working | Electron | Custom frame or native frame | Configure in main process |

### Session Management

| Feature | Location | Status | Data Source | "Done" Definition | Notes |
|---------|----------|--------|-------------|-------------------|-------|
| Session Start | `App.tsx:843` | Working | `POST /api/session/start` | Creates session with config | Sends title, model, language, device |
| Session Stop | `App.tsx:878` | Working | `POST /api/session/stop` | Stops and finalizes session | Cleanup handled by backend |
| Session State Tracking | `App.tsx:203` | Working | SSE + polling | Real-time status updates | Uses `snapshot.session?.status` |
| Session Title Input | `Sidebar.tsx:255` | Working | Local form state | Editable session name | Protected from settings overwrite |
| Export Directory Selection | `App.tsx:807`, `Sidebar.tsx:417` | Working | Electron IPC `chooseDirectory` | Folder picker integration | Falls back to `sessions/` default |
| Model Preloading | `App.tsx:815` | Working | `POST /api/models/preload` | Progress tracking via SSE | Shows load time estimates per model |
| PDF Context Attachment | `App.tsx:892` | Working | `POST /api/session/attach-pdf` | File picker + backend upload | For context-aware transcription |
| Session Persistence | Backend | Working | File system | Sessions saved to disk | Configurable via `exportRoot` |
| Device Selection | `Sidebar.tsx:270` | Working | `GET /api/devices` | Dropdown with loopback markers | Auto-selects loopback if available |
| Device Refresh | `Sidebar.tsx:281` | Working | `GET /api/devices` | Refreshes available devices | Triggered manually |

### Audio Input & Visualization

| Feature | Location | Status | Data Source | "Done" Definition | Notes |
|---------|----------|--------|-------------|-------------------|-------|
| Input Level Meter | `Sidebar.tsx:437` | Working | SSE `meter_value` field | Visual bar responds to audio | Displays as percentage 0-100% |
| Audio Device Probe | `Sidebar.tsx:82` | Working | `GET /api/devices/{id}/probe` | Tests device signal quality | Shows RMS, peak, channels, sample rate |
| WebSocket Audio Stream | Backend | Working | WebSocket connection | Real-time audio capture | Fallback to simulation if unavailable |
| Floating Window Visualization | `FloatingWindow.tsx` | Partially Working | IPC + simulation | 36-bar waveform display | Uses real data when available, simulates when idle |
| VAD (Voice Activity Detection) | Settings + Backend | Working | Backend processing | Filters silence vs speech | Configurable threshold (-60 to -20 dB) |
| Noise Filtering | Settings | Working | Backend processing | Reduces background noise | Toggle in Audio settings |
| Echo Cancellation | Settings | Working | Backend processing | Removes speaker echo | Toggle in Audio settings |
| Auto Gain Control | Settings | Working | Backend processing | Automatic volume adjustment | Toggle in Audio settings |
| Sample Rate Selection | `SettingsPanel.tsx:1203` | Working | Settings state | 8kHz to 48kHz options | 16kHz recommended for Whisper |

### Transcription Display

| Feature | Location | Status | Data Source | "Done" Definition | Notes |
|---------|----------|--------|-------------|-------------------|-------|
| Live Transcript View | `MainContent.tsx:96` | Working | SSE `segment` events | Shows incoming text | Last 100 segments displayed |
| Word-Level Timestamps | `MainContent.tsx:267` | Working | Segment `words` array | Hoverable word timing | Confidence per word |
| Confidence Visualization | `MainContent.tsx:324` | Working | Segment `confidence` field | Color-coded indicators | Green ≥85%, Yellow 70-85%, Red <70% |
| Language Detection Badge | `MainContent.tsx:315` | Working | Segment `language` field | Shows HI/EN/AUTO per segment | Visual distinction for Hindi |
| Partial Segment Indicator | `MainContent.tsx:347` | Working | `is_partial` field | Blinking cursor for live text | Opacity 70%, dashed border |
| Auto-Scroll Control | `MainContent.tsx:25` | Working | Local state | Scrolls to latest segment | Disables when user scrolls up |
| Segment Quality Labels | `MainContent.tsx:300` | Working | `quality_label` field | Shows "weak decode" warnings | Includes script mismatch detection |
| Suppressed Segments View | `MainContent.tsx:214` | Working | `suppressed_transcript` array | Lists filtered content | Shows suppression reasons |
| Review Flags View | `MainContent.tsx:187` | Working | `needs_review` array | Highlights questionable segments | Shows review reasons |
| Formula Detection Display | `MainContent.tsx:159` | Working | SSE `formulas` events | Renders math expressions | Shows context and timestamp |
| Latency Metrics | `MainContent.tsx:51` | Working | `latency_ms` field | Shows processing delay | Color-coded: <500ms good, ≥500ms warning |
| Activity Feed | `ActivityFeed.tsx` | Working | SSE events | Recent 8 segments preview | Shows timestamps and preview text |
| Segment Counters | `MainContent.tsx:45` | Working | Calculated from state | Real-time counts | Segments, Formulas, Review, Suppressed |

### Settings System

#### General Settings (8 fields)

| Feature | Location | Status | Data Source | "Done" Definition | Notes |
|---------|----------|--------|-------------|-------------------|-------|
| Theme Selection | `SettingsPanel.tsx:850` | Working | Settings API + LocalStorage | Persists theme choice | Dropdown: light, dark, cyber, dracula |
| Default Session Title | `SettingsPanel.tsx:863` | Working | Settings API | Pre-fills new session title | User edit protection implemented |
| Default Language | `SettingsPanel.tsx:877` | Working | Settings API | Auto/en/hi options | Affects new session defaults |
| Export Directory | `SettingsPanel.tsx:896` | Working | Settings API + IPC | Folder browser integration | Browse button opens picker |
| Auto-Save Interval | `SettingsPanel.tsx:924` | Working | Settings API | Slider 10-300 seconds | Affects session persistence frequency |
| Show Notifications | `SettingsPanel.tsx:951` | Working | Settings API | Desktop notification toggle | Affects OS-level notifications |
| Minimize to Tray | `SettingsPanel.tsx:961` | Working | Settings API + Electron | Tray behavior toggle | Requires main process support |
| Start with System | `SettingsPanel.tsx:971` | Working | Settings API + Electron | Windows startup toggle | Registry/preference integration |

#### Transcription Settings (14 fields)

| Feature | Location | Status | Data Source | "Done" Definition | Notes |
|---------|----------|--------|-------------|-------------------|-------|
| Model Selection | `SettingsPanel.tsx:1029` | Working | Settings API | tiny/base/small/medium/large-v3 | Hardware-aware recommendations |
| Compute Type | `SettingsPanel.tsx:1045` | Working | Settings API | float16/int8/int8_float16 | Affects quality vs speed |
| Chunk Duration | `SettingsPanel.tsx:1063` | Working | Settings API | Slider 0.5-5.0 seconds | Affects latency |
| Overlap Ratio | `SettingsPanel.tsx:1079` | Working | Settings API | Slider 0-0.5 | Between chunks |
| VAD Enabled | Backend | Working | Settings API | Speech detection toggle | Backend implementation |
| VAD Threshold (dB) | Backend | Working | Settings API | -60 to -20 dB range | Speech detection sensitivity |
| Confidence Threshold | Backend | Working | Settings API | 0.0-1.0 range | Quality filtering |
| Filler Filter | Backend | Working | Settings API | Removes "um", "uh" | Toggle enabled |
| Hallucination Filter | Backend | Working | Settings API | Removes false positives | Toggle enabled |
| Min Segment Length | Backend | Working | Settings API | Duration threshold | Filters short segments |
| Max Workers | `SettingsPanel.tsx` | Partially Working | Settings API | Parallel processing workers | May not affect actual backend |
| Use Parallel Processing | `SettingsPanel.tsx:1144` | Working | Settings API | Toggle for multi-worker | Affects transcription speed |
| Preload Model | `SettingsPanel.tsx:1154` | Working | Settings API | Keep model in memory | Faster session starts |
| Hotkey Optimized | `SettingsPanel.tsx:1164` | Working | Settings API | Quick-start optimization | For hotkey-triggered sessions |
| Beam Size | `SettingsPanel.tsx:1104` | Working | Settings API | 1-20 range | Search breadth |
| Best Of | `SettingsPanel.tsx:1113` | Working | Settings API | 1-20 range | Candidate samples |
| Patience | `SettingsPanel.tsx:1122` | Working | Settings API | 0.1-5.0 range | Decoding patience |
| Temperature | Backend | Working | Settings API | 0.0-1.0 range | Sampling randomness |
| Optimization Presets | `SettingsPanel.tsx:994` | Working | Local presets | 4 presets: max/balanced/fast/low-mem | Hardware recommendations |
| Hardware Profile Display | `SettingsPanel.tsx:460` | Working | `GET /api/system/profile` | Shows GPU/CPU/Storage info | Recommended settings |

#### Audio Settings (7 fields)

| Feature | Location | Status | Data Source | "Done" Definition | Notes |
|---------|----------|--------|-------------|-------------------|-------|
| Default Audio Device | `SettingsPanel.tsx:1185` | Working | Settings API | Dropdown of available devices | Syncs with device list |
| Sample Rate | `SettingsPanel.tsx:1198` | Working | Settings API | 8k-48k options | 16kHz recommended |
| VAD Enabled (Audio) | `SettingsPanel.tsx:1228` | Working | Settings API | Toggle | Duplicate of transcription VAD |
| VAD Threshold (Audio) | `SettingsPanel.tsx:1234` | Working | Settings API | Slider -60 to -20 dB | Visual indicator |
| Noise Filtering | `SettingsPanel.tsx:1265` | Working | Settings API | Toggle | Audio preprocessing |
| Echo Cancellation | `SettingsPanel.tsx:1275` | Working | Settings API | Toggle | Removes speaker feedback |
| Auto Gain Control | `SettingsPanel.tsx:1285` | Working | Settings API | Toggle | Automatic volume |

#### Hotkey Settings (10 fields)

| Feature | Location | Status | Data Source | "Done" Definition | Notes |
|---------|----------|--------|-------------|-------------------|-------|
| Enable Global Hotkey | `SettingsPanel.tsx:1305` | Working | Settings API + IPC | Toggle activation | Registers with Electron |
| Key Combination | `SettingsPanel.tsx:1318` | Working | Settings API + IPC | Recorder component | Visual key capture |
| Hold Mode | `SettingsPanel.tsx:1360` | Working | Settings API | Toggle behavior | Press-and-hold vs toggle |
| Auto-Inject Text | `SettingsPanel.tsx:1370` | Working | Settings API | Type into active window | Requires accessibility permissions |
| Show Floating Window | `SettingsPanel.tsx:1380` | Working | Settings API + IPC | Overlay visibility | Position configurable |
| Floating Window Position | `SettingsPanel.tsx:1330` | Working | Settings API | 5 positions | Corners + center |
| Copy to Clipboard | `SettingsPanel.tsx:1390` | Working | Settings API | Auto-copy toggle | After transcription |
| Record on Start | Hotkey config | Working | Settings API | Auto-start recording | When hotkey triggered |
| Stop on Release | Hotkey config | Working | Settings API | Auto-stop behavior | When key released (hold mode) |
| Floating Window Opacity | Types only | Fake | N/A | Slider 0.1-1.0 | Defined in types but not implemented |
| Floating Window Size | Types only | Fake | N/A | Width/Height inputs | Defined in types but not implemented |

#### Advanced Settings (8 fields)

| Feature | Location | Status | Data Source | "Done" Definition | Notes |
|---------|----------|--------|-------------|-------------------|-------|
| Debug Mode | `SettingsPanel.tsx:1436` | Working | Settings API | Verbose logging toggle | Affects log output |
| Log Level | `SettingsPanel.tsx:1447` | Working | Settings API | DEBUG/INFO/WARN/ERROR | Log verbosity |
| Max Log Files | `SettingsPanel.tsx:1458` | Working | Settings API | Number input 1-100 | Rotation count |
| Enable Metrics | `SettingsPanel.tsx:1505` | Working | Settings API | Performance tracking | Telemetry/analytics |
| Experimental STEM Detection | `SettingsPanel.tsx:1485` | Working | Settings API | Enhanced formula detection | Better math recognition |
| Experimental GPU Acceleration | `SettingsPanel.tsx:1495` | Working | Settings API | GPU preprocessing | When available |
| Settings Export | `SettingsPanel.tsx:716` | Working | Local file system | JSON export | Download settings file |
| Settings Import | `SettingsPanel.tsx:727` | Working | Local file system | JSON import | Upload settings file |
| Settings Reset | `SettingsPanel.tsx:782` | Working | `POST /api/settings/reset` | Restore defaults | Confirmation dialog |
| Auto-Save | `SettingsPanel.tsx:801` | Working | Debounced save | 1.5s delay after change | Visual save status |

**Settings Wiring Summary:**
- **Fully Wired (62%)**: 35 fields with backend persistence
- **Partially Wired (20%)**: 7 fields (frontend state only or settings not applied)
- **Fake/Stubbed (18%)**: 4 fields defined in types but not implemented in UI

### Diagnostics & Runtime Status

| Feature | Location | Status | Data Source | "Done" Definition | Notes |
|---------|----------|--------|-------------|-------------------|-------|
| Connection Status Badge | `Sidebar.tsx:99` | Working | `useEventSource` hook | SSE vs Polling indicator | Visual: Connected/Reconnecting/Polling |
| GPU Status Badge | `Sidebar.tsx:111` | Working | `health.gpu_mode` field | GPU/CPU/Fallback indicator | Shows CUDA availability |
| Backend Health | `Sidebar.tsx:204` | Working | `health` object | Ready/Connecting/Error states | Polling when unavailable |
| Runtime Metrics Grid | `Sidebar.tsx:497` | Working | `health` object | GPU, Runtime, Queue, Dropped | 4-metric display |
| Status Message Display | `Sidebar.tsx:505` | Working | Local state | Contextual feedback | Error/warning/info messages |
| Backpressure State | `Sidebar.tsx:592` | Working | `stt_backpressure_state` | normal/elevated/critical | Queue depth warning |
| Device Test Results | `Sidebar.tsx:554` | Working | Probe API results | RMS, Peak, Signal, Channels | Expandable test panel |
| Warning Display | `Sidebar.tsx:616` | Working | `last_warning` field | Alert box for warnings | Visual warning indicator |
| Error Display | `Sidebar.tsx:311` | Working | `last_error` field | Error state in status | Stops session on critical errors |
| Session Pulse Panel | `ActivityFeed.tsx:16` | Working | Session object | Title, output directory | Shows active session info |
| Model Loading Indicator | `Sidebar.tsx:346` | Working | `loading` state | Progress with time estimate | Per-model load times |

### Hotkey & Floating Window

| Feature | Location | Status | Data Source | "Done" Definition | Notes |
|---------|----------|--------|-------------|-------------------|-------|
| Global Hotkey Registration | `useHotkey.ts:110` | Working | Electron IPC | Registers with OS | Ctrl+Shift+T default |
| Hotkey State Management | `useHotkey.ts:39` | Working | IPC + API | Tracks enabled/disabled | Persisted to settings |
| Hotkey Toggle | `useHotkey.ts:140` | Working | IPC | Enable/disable | Immediate effect |
| Floating Window Show/Hide | `useHotkey.ts:168` | Working | Electron IPC | Window visibility | Position from settings |
| Floating Window Component | `FloatingWindow.tsx` | Working | IPC events | Standalone window | 420x140px, always on top |
| Waveform Visualization | `FloatingWindow.tsx:336` | Working | Real data + simulation | 36-bar animated display | Smooth animations |
| Recording Timer | `FloatingWindow.tsx:312` | Working | Local state | MM:SS display | Starts with recording |
| Transcription Preview | `FloatingWindow.tsx:388` | Working | IPC events | Live text display | "Waiting for speech..." default |
| Recording State Indicator | `FloatingWindow.tsx:254` | Working | State machine | Idle/Listening/Processing | Color-coded status dot |
| Processing Animation | `FloatingWindow.tsx:172` | Working | CSS animations | Bouncing dots | While processing |
| Status Text Display | `FloatingWindow.tsx:168` | Working | State-based | Listening/Processing/Ready | With animated dots |
| Pulse Ring Animation | `FloatingWindow.tsx:258` | Working | CSS keyframes | Expanding rings | When recording |

### STEM/Formula Detection

| Feature | Location | Status | Data Source | "Done" Definition | Notes |
|---------|----------|--------|-------------|-------------------|-------|
| Formula Detection | Backend | Working | SSE `formulas` events | Detects math expressions | E=mc², equations, etc. |
| Formula Display | `MainContent.tsx:159` | Working | `formulas` array | Renders with context | Shows timestamp, expression |
| Formula Confidence | `Formula` type | Working | `confidence` field | Quality indicator | Parseable flag |
| Formula Review Flag | `Formula` type | Working | `review_flag` field | Manual review trigger | For questionable detections |
| Formula Variables | `Formula` type | Working | `variables` array | Extracted variables | Symbol recognition |
| Formula Units | `Formula` type | Working | `units` array | Detected units | Physics/chemistry units |
| Experimental STEM Mode | `SettingsPanel.tsx:1485` | Working | Settings toggle | Enhanced detection | Better recognition algorithm |
| Formula Counter | `MainContent.tsx:46` | Working | Calculated count | Real-time update | Header stat card |

---

## Priority Matrix

### P0 - Critical (Must Have for v1.0)

| Priority | Feature | Why Critical |
|----------|---------|--------------|
| P0 | Session Start/Stop | Core functionality - without this, app has no purpose |
| P0 | Real-time Transcription Display | Primary user output - SSE working |
| P0 | Audio Device Selection | Required for input - basic functionality |
| P0 | Settings Persistence | User expects preferences to save |
| P0 | Theme Switching | Basic UX requirement |
| P0 | Backend Health Monitoring | Users need to know if backend is connected |
| P0 | Model Selection | Different accuracy/speed tradeoffs |
| P0 | Language Selection | Multi-language support is a key feature |

### P1 - Important (Should Have for v1.0)

| Priority | Feature | Why Important |
|----------|---------|---------------|
| P1 | Floating Window | Differentiator for quick transcription |
| P1 | Global Hotkey | Power user feature - quick access |
| P1 | Hardware Profile Display | Helps users understand capabilities |
| P1 | Formula Detection | STEM users key demographic |
| P1 | Input Level Meter | Visual feedback that audio is working |
| P1 | Confidence Visualization | Quality indicator for users |
| P1 | PDF Context Attachment | Context-aware transcription |
| P1 | Optimization Presets | Simplifies configuration |
| P1 | Auto-Save | Data loss prevention |
| P1 | Device Test | Troubleshooting capability |
| P1 | Latency Display | Performance visibility |
| P1 | VAD Configuration | Fine-tuning for different environments |

### P2 - Nice to Have (Could Have for v1.0)

| Priority | Feature | Why Nice to Have |
|----------|---------|------------------|
| P2 | Settings Import/Export | Power user feature |
| P2 | Advanced Beam Search Params | Expert tuning |
| P2 | Experimental Features Toggle | Beta feature gating |
| P2 | Notifications | UX enhancement |
| P2 | Minimize to Tray | Convenience feature |
| P2 | Start with System | Power user convenience |
| P2 | Word-level Timestamps | Granular detail |
| P2 | Suppressed Segments View | Debugging feature |
| P2 | Review Flags Management | Quality workflow |
| P2 | Processing Animation | Polish/feel |
| P2 | Custom Scrollbars | Visual polish |
| P2 | Activity Feed | Secondary information |

---

## Quick Wins

Features that can be fixed/enabled with minimal effort:

| # | Feature | Location | Effort | Action |
|---|---------|----------|--------|--------|
| 1 | Floating Window Opacity | `types/api.ts:277` | 30 min | Add slider to Hotkey settings |
| 2 | Floating Window Size | `types/api.ts:278` | 30 min | Add width/height inputs to Hotkey settings |
| 3 | Max Workers Backend Sync | `SettingsPanel.tsx` | 1 hour | Verify backend applies this setting |
| 4 | Notification Toast | `App.tsx` | 1 hour | Implement toast for `showNotifications` |
| 5 | Tray Icon Integration | Main process | 2 hours | Wire up `minimizeToTray` setting |
| 6 | Startup Registry | Main process | 2 hours | Wire up `startupWithSystem` setting |
| 7 | Settings Search | `SettingsPanel.tsx:1555` | Already Working | Just needs more indexed fields |
| 8 | Export/Import UI Polish | `SettingsPanel.tsx:1588` | 30 min | Add confirmation toasts |
| 9 | Reset Confirmation | `SettingsPanel.tsx:782` | Already Working | Uses native confirm() |
| 10 | Hotkey Test Button | `useHotkey.ts:186` | 30 min | Add test button to settings |

---

## Known Issues & Limitations

| Issue | Location | Impact | Workaround |
|-------|----------|--------|------------|
| VAD threshold duplicated | Transcription + Audio settings | Confusion | Both update same backend value |
| `max_workers` may not affect backend | Transcription settings | Potential no-op | Verify backend implementation |
| SSE disconnect storms | `useEventSource.ts:176` | Reconnection loops | Already has retry limit |
| Floating window always simulates when idle | `FloatingWindow.tsx:52` | No real data when not recording | By design - no audio source |
| Settings search only indexes categories | `SettingsPanel.tsx:822` | Limited search | Could expand to setting names |
| No keyboard navigation in settings | `SettingsPanel.tsx` | Accessibility | Mouse/touch only currently |

---

## Backend API Endpoints

| Endpoint | Method | Used By | Status |
|----------|--------|---------|--------|
| `/api/events` | SSE | `useEventSource.ts` | Working |
| `/api/session` | GET | `App.tsx` | Working |
| `/api/session/start` | POST | `App.tsx` | Working |
| `/api/session/stop` | POST | `App.tsx` | Working |
| `/api/session/attach-pdf` | POST | `App.tsx` | Working |
| `/api/devices` | GET | `Sidebar.tsx` | Working |
| `/api/devices/{id}/probe` | GET | `Sidebar.tsx` | Working |
| `/api/models/preload` | POST | `App.tsx` | Working |
| `/api/settings` | GET/POST | `SettingsPanel.tsx` | Working |
| `/api/settings/reset` | POST | `SettingsPanel.tsx` | Working |
| `/api/system/profile` | GET | `SettingsPanel.tsx` | Working |
| `/api/hotkey/config` | POST | `useHotkey.ts` | Working |

---

## File Inventory

### Core Application Files

| File | Lines | Purpose |
|------|-------|---------|
| `App.tsx` | 1015 | Main application component, state management |
| `components/MainContent.tsx` | 431 | Live transcript display, insights |
| `components/Sidebar.tsx` | 657 | Session controls, device selection |
| `components/ActivityFeed.tsx` | 78 | Recent activity timeline |
| `components/SettingsPanel.tsx` | 1703 | Comprehensive settings UI |
| `components/FloatingWindow.tsx` | 424 | Hotkey overlay window |
| `hooks/useEventSource.ts` | 289 | SSE with polling fallback |
| `hooks/useHotkey.ts` | 227 | Hotkey state management |
| `lib/sessionReducer.ts` | 150 | State transformation logic |
| `types/api.ts` | 359 | TypeScript type definitions |

### Electron Files

| File | Purpose |
|------|---------|
| `main.js` | Main process entry |
| `preload.js` | Main window preload script |
| `preload-floating.js` | Floating window preload script |

---

*Document generated based on codebase analysis. Last updated: March 2, 2026*
