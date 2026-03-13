# Changes Since Last Commit

Generated: 2026-03-03T04:50:12.935Z
Base commit: ddd466c

## Git Status

```text
M  .env.example
M  .gitignore
AM CHANGELOG.md
AM CONTRIBUTING.md
MM README.md
A  app/api/model_service.py
MM app/api/server.py
M  app/api/service.py
 M app/audio/__init__.py
A  app/audio/backends/__init__.py
A  app/audio/backends/base.py
A  app/audio/backends/factory.py
A  app/audio/backends/pyaudio_wasapi.py
A  app/audio/backends/soundcard_backend.py
M  app/audio/capture.py
M  app/audio/devices.py
A  app/config/__init__.py
AM app/config/constants.py
A  app/config/settings.py
A  app/config/text.py
 M app/core/__init__.py
MM app/core/config.py
A  app/core/constants.py
M  app/core/language_profiles.py
A  app/core/model_catalog.py
M  app/core/models.py
M  app/core/session_manager.py
MM app/core/settings_manager.py
A  app/core/settings_migrations.py
A  app/core/settings_validator.py
A  app/electron/.gitignore
R  ui-electron/floating-window.html -> app/electron/floating-window.html
R  ui-electron/frontend/floating.html -> app/electron/frontend/floating.html
R  ui-electron/frontend/index.html -> app/electron/frontend/index.html
RM ui-electron/frontend/package-lock.json -> app/electron/frontend/package-lock.json
RM ui-electron/frontend/package.json -> app/electron/frontend/package.json
R  ui-electron/frontend/postcss.config.cjs -> app/electron/frontend/postcss.config.cjs
RM ui-electron/frontend/src/App.tsx -> app/electron/frontend/src/App.tsx
A  app/electron/frontend/src/components/ActivityFeed.tsx
R  ui-electron/frontend/src/components/AdvancedSettings.tsx -> app/electron/frontend/src/components/AdvancedSettings.tsx
A  app/electron/frontend/src/components/ErrorBoundary.tsx
RM ui-electron/frontend/src/components/FloatingWindow.tsx -> app/electron/frontend/src/components/FloatingWindow.tsx
RM ui-electron/frontend/src/components/HotkeySettings.tsx -> app/electron/frontend/src/components/HotkeySettings.tsx
A  app/electron/frontend/src/components/MainContent.tsx
RM ui-electron/frontend/src/components/SettingsPanel.tsx -> app/electron/frontend/src/components/SettingsPanel.tsx
R  ui-electron/frontend/src/components/Sidebar.tsx -> app/electron/frontend/src/components/Sidebar.tsx
AM app/electron/frontend/src/config/settings.ts
AM app/electron/frontend/src/config/text.ts
R  ui-electron/frontend/src/floating-main.tsx -> app/electron/frontend/src/floating-main.tsx
RM ui-electron/frontend/src/hooks/useEventSource.ts -> app/electron/frontend/src/hooks/useEventSource.ts
R  ui-electron/frontend/src/hooks/useHotkey.ts -> app/electron/frontend/src/hooks/useHotkey.ts
R  ui-electron/frontend/src/index.css -> app/electron/frontend/src/index.css
AM app/electron/frontend/src/lib/constants.ts
A  app/electron/frontend/src/lib/languages.ts
AM app/electron/frontend/src/lib/modelRegistry.test.ts
A  app/electron/frontend/src/lib/modelRegistry.ts
R  ui-electron/frontend/src/lib/sessionReducer.ts -> app/electron/frontend/src/lib/sessionReducer.ts
A  app/electron/frontend/src/lib/settingsMigration.ts
AM app/electron/frontend/src/lib/settingsSchema.ts
R  ui-electron/frontend/src/main.tsx -> app/electron/frontend/src/main.tsx
AM app/electron/frontend/src/services/healthService.ts
RM ui-electron/frontend/src/types/api.ts -> app/electron/frontend/src/types/api.ts
R  ui-electron/frontend/src/vite-env.d.ts -> app/electron/frontend/src/vite-env.d.ts
R  ui-electron/frontend/tailwind.config.cjs -> app/electron/frontend/tailwind.config.cjs
RM ui-electron/frontend/tsconfig.json -> app/electron/frontend/tsconfig.json
R  ui-electron/frontend/tsconfig.node.json -> app/electron/frontend/tsconfig.node.json
RM ui-electron/frontend/vite.config.ts -> app/electron/frontend/vite.config.ts
AM app/electron/frontend/vitest.config.ts
AM app/electron/main/config.js
AM app/electron/main/index.js
AM app/electron/main/ipc/handlers.js
AM app/electron/main/ipc/hotkeyHandlers.js
AM app/electron/main/main.js
AM app/electron/main/model-download-manager.js
R  ui-electron/preload-floating.js -> app/electron/main/preload-floating.js
A  app/electron/main/preload-quick-settings.js
R  ui-electron/preload.js -> app/electron/main/preload.js
AM app/electron/main/services/backendSpawn.js
A  app/electron/main/services/textInjector.js
AM app/electron/main/shared/state.js
AM app/electron/main/utils/api.js
AM app/electron/main/windows/floatingWindow.js
A  app/electron/main/windows/mainWindow.js
A  app/electron/main/windows/quickSettingsWindow.js
AM app/electron/main/windows/tray.js
RM ui-electron/package-lock.json -> app/electron/package-lock.json
RM ui-electron/package.json -> app/electron/package.json
A  app/electron/quick-settings.html
R  ui-electron/scripts/build-frontend.js -> app/electron/scripts/build-frontend.js
R  ui-electron/scripts/dev.js -> app/electron/scripts/dev.js
 M app/stt/__init__.py
M  app/stt/chunker.py
A  app/stt/dictation_cleanup.py
M  app/stt/engine.py
M  app/stt/fast_chunker.py
MM app/stt/fast_engine.py
M  app/stt/quality.py
A  app/ui/README.md
AD config/__init__.py
AD config/generate_ts.py
AD config/python/constants.py
AD config/python/text.py
AD config/shared/index.ts
AD config/typescript/constants.ts
AD config/typescript/text.ts
AD docs/COMPLETION_REPORT.md
AD docs/PROJECT_STRUCTURE.md
A  docs/api/endpoints.md
RD docs/ARCHITECTURE_PLAN.md -> docs/architecture/ARCHITECTURE_PLAN.md
RD .github/AUDIT_REPORT.md -> docs/architecture/AUDIT_REPORT.md
AD docs/architecture/FEATURE_INVENTORY.md
AD docs/architecture/IMPLEMENTATION_SUMMARY.md
AD docs/audit/AUDIT_REPORT.md
RM docs/DEPLOYMENT.md -> docs/deployment/DEPLOYMENT.md
AD docs/operations/FIXES_SUMMARY.md
RM docs/OPERATIONS.md -> docs/operations/OPERATIONS.md
AM docs/operations/TESTING.md
AD docs/operations/VERIFICATION_CHECKLIST.md
RM AGENTS.md -> docs/project/AGENTS.md
AM docs/project/CHECKLIST.md
AD docs/project/SETTINGS_REFACTOR_SUMMARY.md
AD logs/session.jsonl
MM package.json
MM pyproject.toml
MM requirements.txt
MD scripts/README.md
 D scripts/check_cuda.py
 D scripts/install_pytorch_cuda.ps1
 M tests/conftest.py
A  tests/test_dictation_cleanup.py
A  tests/test_fixes.py
A  tests/test_model_catalog.py
A  tests/test_settings_manager.py
RD test_audio_capture.py -> tools/debug/test_audio_capture.py
AD tools/mic_diagnostic.py
AD tools/verify_fixes.py
AD tools/verify_frontend.ts
D  ui-electron/frontend/src/components/ActivityFeed.tsx
D  ui-electron/frontend/src/components/MainContent.tsx
D  ui-electron/main.js
D  ui-electron/src/main/main.js
D  ui-electron/src/main/preload.js
?? app/api/refiner_service.py
?? app/api/settings_sync.py
?? app/api/websocket_server.py
?? app/audio/audio_processing.py
?? app/audio/pipeline_base.py
?? app/audio/pipeline_factory.py
?? app/audio/system_pipeline.py
?? app/audio/vad_optimized.py
?? app/audio/wispr_pipeline.py
?? app/config/generate_ts.py
?? app/core/error_handler.py
?? app/core/hotkey_session.py
?? app/core/metrics.py
?? app/core/mode_manager.py
?? app/core/modes.py
?? app/core/performance_monitor.py
?? app/core/recovery_strategies.py
?? app/core/system_session.py
?? app/core/tests/
?? app/electron/frontend/.github/
?? app/electron/frontend/.nycrc.json
?? app/electron/frontend/src/components/AudioVisualizer.test.tsx
?? app/electron/frontend/src/components/AudioVisualizer.tsx
?? app/electron/frontend/src/components/HotkeySettings.test.tsx
?? app/electron/frontend/src/components/ModeSelector.test.tsx
?? app/electron/frontend/src/components/ModeSelector.tsx
?? app/electron/frontend/src/components/ModeSettings.test.tsx
?? app/electron/frontend/src/components/ModeSettings.tsx
?? app/electron/frontend/src/components/PartialText.test.tsx
?? app/electron/frontend/src/components/PartialText.tsx
?? app/electron/frontend/src/components/TranscriptionStream.tsx
?? app/electron/frontend/src/components/__tests__/
?? app/electron/frontend/src/components/settings/
?? app/electron/frontend/src/config/generated/
?? app/electron/frontend/src/config/index.ts
?? app/electron/frontend/src/context/
?? app/electron/frontend/src/hooks/__tests__/
?? app/electron/frontend/src/hooks/useSettingsSync.ts
?? app/electron/frontend/src/hooks/useWebSocket.test.ts
?? app/electron/frontend/src/hooks/useWebSocket.ts
?? app/electron/frontend/src/lib/sessionReducer.test.ts
?? app/electron/frontend/src/lib/settingsApi.test.ts
?? app/electron/frontend/src/lib/settingsApi.ts
?? app/electron/frontend/src/test/
?? app/electron/frontend/test-results/
?? app/electron/main/windows/trayUtils.js
?? app/stt/fast_whisper_backend.py
?? app/stt/model_pool.py
?? app/stt/streaming_engine.py
?? docs/ARCHITECTURE.md
?? docs/OPTIMIZATION_SUMMARY.md
?? docs/README.md
?? docs/architecture/OPTIMIZATION_ROADMAP.md
?? docs/architecture/architecture-plan.md
?? docs/architecture/feature-inventory.md
?? docs/architecture/implementation-summary.md
?? docs/audits/
?? docs/operations/fixes-summary.md
?? docs/operations/verification-checklist.md
?? docs/project/completion-report.md
?? docs/project/project-structure.md
?? docs/project/settings-refactor-summary.md
?? e2e/
?? pnpm-lock.yaml
?? pytest.ini
?? reports/
?? scripts/build.py
?? scripts/generate-changes-since-last-commit.cjs
?? scripts/generate-tree.cjs
?? scripts/validate.py
?? tests/README.md
?? tests/integration/
?? tests/performance/
?? tests/test_audio_pipelines.py
?? tests/test_error_handling.py
?? tests/test_hotkey_session.py
?? tests/test_mode_manager.py
?? tests/test_refiner_service.py
?? tests/test_system_session.py
?? tests/test_vad_optimized.py
?? tests/unit/
?? tools/README.md
?? tools/ci/
?? tools/diagnostics/
?? tools/maintenance/
?? tools/runner.py
?? tools/setup/
```

## Changed Files vs HEAD

```text
M	.env.example
D	.github/AUDIT_REPORT.md
M	.gitignore
A	CHANGELOG.md
A	CONTRIBUTING.md
M	README.md
A	app/api/model_service.py
M	app/api/server.py
M	app/api/service.py
M	app/audio/__init__.py
A	app/audio/backends/__init__.py
A	app/audio/backends/base.py
A	app/audio/backends/factory.py
A	app/audio/backends/pyaudio_wasapi.py
A	app/audio/backends/soundcard_backend.py
M	app/audio/capture.py
M	app/audio/devices.py
A	app/config/__init__.py
A	app/config/constants.py
A	app/config/settings.py
A	app/config/text.py
M	app/core/__init__.py
M	app/core/config.py
A	app/core/constants.py
M	app/core/language_profiles.py
A	app/core/model_catalog.py
M	app/core/models.py
M	app/core/session_manager.py
M	app/core/settings_manager.py
A	app/core/settings_migrations.py
A	app/core/settings_validator.py
A	app/electron/.gitignore
R067	ui-electron/floating-window.html	app/electron/floating-window.html
R100	ui-electron/frontend/floating.html	app/electron/frontend/floating.html
R100	ui-electron/frontend/index.html	app/electron/frontend/index.html
R057	ui-electron/frontend/package-lock.json	app/electron/frontend/package-lock.json
A	app/electron/frontend/package.json
R100	ui-electron/frontend/postcss.config.cjs	app/electron/frontend/postcss.config.cjs
R061	ui-electron/frontend/src/App.tsx	app/electron/frontend/src/App.tsx
A	app/electron/frontend/src/components/ActivityFeed.tsx
R082	ui-electron/frontend/src/components/AdvancedSettings.tsx	app/electron/frontend/src/components/AdvancedSettings.tsx
A	app/electron/frontend/src/components/ErrorBoundary.tsx
R079	ui-electron/frontend/src/components/FloatingWindow.tsx	app/electron/frontend/src/components/FloatingWindow.tsx
R069	ui-electron/frontend/src/components/HotkeySettings.tsx	app/electron/frontend/src/components/HotkeySettings.tsx
A	app/electron/frontend/src/components/MainContent.tsx
A	app/electron/frontend/src/components/SettingsPanel.tsx
R080	ui-electron/frontend/src/components/Sidebar.tsx	app/electron/frontend/src/components/Sidebar.tsx
A	app/electron/frontend/src/config/settings.ts
A	app/electron/frontend/src/config/text.ts
R100	ui-electron/frontend/src/floating-main.tsx	app/electron/frontend/src/floating-main.tsx
R082	ui-electron/frontend/src/hooks/useEventSource.ts	app/electron/frontend/src/hooks/useEventSource.ts
R074	ui-electron/frontend/src/hooks/useHotkey.ts	app/electron/frontend/src/hooks/useHotkey.ts
R100	ui-electron/frontend/src/index.css	app/electron/frontend/src/index.css
A	app/electron/frontend/src/lib/constants.ts
A	app/electron/frontend/src/lib/languages.ts
A	app/electron/frontend/src/lib/modelRegistry.test.ts
A	app/electron/frontend/src/lib/modelRegistry.ts
R095	ui-electron/frontend/src/lib/sessionReducer.ts	app/electron/frontend/src/lib/sessionReducer.ts
A	app/electron/frontend/src/lib/settingsMigration.ts
A	app/electron/frontend/src/lib/settingsSchema.ts
R063	ui-electron/frontend/src/main.tsx	app/electron/frontend/src/main.tsx
A	app/electron/frontend/src/services/healthService.ts
R051	ui-electron/frontend/src/types/api.ts	app/electron/frontend/src/types/api.ts
R075	ui-electron/frontend/src/vite-env.d.ts	app/electron/frontend/src/vite-env.d.ts
R088	ui-electron/frontend/tailwind.config.cjs	app/electron/frontend/tailwind.config.cjs
R086	ui-electron/frontend/tsconfig.json	app/electron/frontend/tsconfig.json
R100	ui-electron/frontend/tsconfig.node.json	app/electron/frontend/tsconfig.node.json
R100	ui-electron/frontend/vite.config.ts	app/electron/frontend/vite.config.ts
A	app/electron/frontend/vitest.config.ts
A	app/electron/main/config.js
A	app/electron/main/index.js
A	app/electron/main/ipc/handlers.js
A	app/electron/main/ipc/hotkeyHandlers.js
A	app/electron/main/main.js
A	app/electron/main/model-download-manager.js
R076	ui-electron/preload-floating.js	app/electron/main/preload-floating.js
A	app/electron/main/preload-quick-settings.js
R081	ui-electron/preload.js	app/electron/main/preload.js
A	app/electron/main/services/backendSpawn.js
A	app/electron/main/services/textInjector.js
A	app/electron/main/shared/state.js
A	app/electron/main/utils/api.js
A	app/electron/main/windows/floatingWindow.js
A	app/electron/main/windows/mainWindow.js
A	app/electron/main/windows/quickSettingsWindow.js
A	app/electron/main/windows/tray.js
R075	ui-electron/package-lock.json	app/electron/package-lock.json
R058	ui-electron/package.json	app/electron/package.json
A	app/electron/quick-settings.html
R100	ui-electron/scripts/build-frontend.js	app/electron/scripts/build-frontend.js
R100	ui-electron/scripts/dev.js	app/electron/scripts/dev.js
M	app/stt/__init__.py
M	app/stt/chunker.py
A	app/stt/dictation_cleanup.py
M	app/stt/engine.py
M	app/stt/fast_chunker.py
M	app/stt/fast_engine.py
M	app/stt/quality.py
A	app/ui/README.md
D	docs/ARCHITECTURE_PLAN.md
A	docs/api/endpoints.md
R095	docs/DEPLOYMENT.md	docs/deployment/DEPLOYMENT.md
R099	docs/OPERATIONS.md	docs/operations/OPERATIONS.md
A	docs/operations/TESTING.md
R098	AGENTS.md	docs/project/AGENTS.md
A	docs/project/CHECKLIST.md
M	package.json
M	pyproject.toml
M	requirements.txt
D	scripts/README.md
D	scripts/check_cuda.py
D	scripts/install_pytorch_cuda.ps1
D	test_audio_capture.py
M	tests/conftest.py
A	tests/test_dictation_cleanup.py
A	tests/test_fixes.py
A	tests/test_model_catalog.py
A	tests/test_settings_manager.py
D	ui-electron/frontend/package.json
D	ui-electron/frontend/src/components/ActivityFeed.tsx
D	ui-electron/frontend/src/components/MainContent.tsx
D	ui-electron/frontend/src/components/SettingsPanel.tsx
D	ui-electron/main.js
D	ui-electron/src/main/main.js
D	ui-electron/src/main/preload.js
```

## Diff Stat vs HEAD

```text
.env.example                                       |   40 +-
 .github/AUDIT_REPORT.md                            |  673 -------
 .gitignore                                         |    4 +-
 CHANGELOG.md                                       |   62 +
 CONTRIBUTING.md                                    |  110 ++
 README.md                                          |  102 +-
 app/api/model_service.py                           |  108 +
 app/api/server.py                                  |  923 ++++++++-
 app/api/service.py                                 |  119 +-
 app/audio/__init__.py                              |   36 +-
 app/audio/backends/__init__.py                     |   10 +
 app/audio/backends/base.py                         |  162 ++
 app/audio/backends/factory.py                      |   69 +
 app/audio/backends/pyaudio_wasapi.py               |  284 +++
 app/audio/backends/soundcard_backend.py            |  169 ++
 app/audio/capture.py                               |  486 ++---
 app/audio/devices.py                               |  299 ++-
 app/config/__init__.py                             |  131 ++
 app/config/constants.py                            |  379 ++++
 app/config/settings.py                             |  832 ++++++++
 app/config/text.py                                 |  469 +++++
 app/core/__init__.py                               |   91 +
 app/core/config.py                                 |  402 +++-
 app/core/constants.py                              |  374 ++++
 app/core/language_profiles.py                      |  277 +--
 app/core/model_catalog.py                          |  266 +++
 app/core/models.py                                 |    9 +
 app/core/session_manager.py                        |   18 +
 app/core/settings_manager.py                       |  653 +++++-
 app/core/settings_migrations.py                    |  201 ++
 app/core/settings_validator.py                     |  425 ++++
 app/electron/.gitignore                            |    2 +
 {ui-electron => app/electron}/floating-window.html |  174 +-
 .../electron}/frontend/floating.html               |    0
 {ui-electron => app/electron}/frontend/index.html  |    0
 .../electron}/frontend/package-lock.json           | 2077 +++++++++++++++++++-
 app/electron/frontend/package.json                 |   49 +
 .../electron}/frontend/postcss.config.cjs          |    0
 {ui-electron => app/electron}/frontend/src/App.tsx |  446 +++--
 .../frontend/src/components/ActivityFeed.tsx       |  102 +
 .../frontend/src/components/AdvancedSettings.tsx   |  136 +-
 .../frontend/src/components/ErrorBoundary.tsx      |   68 +
 .../frontend/src/components/FloatingWindow.tsx     |  136 +-
 .../frontend/src/components/HotkeySettings.tsx     |  245 ++-
 .../frontend/src/components/MainContent.tsx        |  547 ++++++
 .../frontend/src/components/SettingsPanel.tsx      |  457 +++++
 .../electron}/frontend/src/components/Sidebar.tsx  |  197 +-
 app/electron/frontend/src/config/settings.ts       |    9 +
 app/electron/frontend/src/config/text.ts           |    8 +
 .../electron}/frontend/src/floating-main.tsx       |    0
 .../electron}/frontend/src/hooks/useEventSource.ts |   47 +-
 .../electron}/frontend/src/hooks/useHotkey.ts      |   96 +-
 .../electron}/frontend/src/index.css               |    0
 app/electron/frontend/src/lib/constants.ts         |    8 +
 app/electron/frontend/src/lib/languages.ts         |   47 +
 .../frontend/src/lib/modelRegistry.test.ts         |  304 +++
 app/electron/frontend/src/lib/modelRegistry.ts     |   68 +
 .../electron}/frontend/src/lib/sessionReducer.ts   |    2 +-
 app/electron/frontend/src/lib/settingsMigration.ts |  207 ++
 app/electron/frontend/src/lib/settingsSchema.ts    |  476 +++++
 .../electron}/frontend/src/main.tsx                |    5 +-
 .../frontend/src/services/healthService.ts         |   54 +
 .../electron}/frontend/src/types/api.ts            |  346 ++--
 .../electron}/frontend/src/vite-env.d.ts           |   18 +-
 .../electron}/frontend/tailwind.config.cjs         |    7 +
 .../electron}/frontend/tsconfig.json               |    8 +-
 .../electron}/frontend/tsconfig.node.json          |    0
 .../electron}/frontend/vite.config.ts              |    0
 app/electron/frontend/vitest.config.ts             |   61 +
 app/electron/main/config.js                        |   45 +
 app/electron/main/index.js                         |   95 +
 app/electron/main/ipc/handlers.js                  |  318 +++
 app/electron/main/ipc/hotkeyHandlers.js            |  258 +++
 app/electron/main/main.js                          | 1925 ++++++++++++++++++
 app/electron/main/model-download-manager.js        |  464 +++++
 .../electron/main}/preload-floating.js             |   15 +-
 app/electron/main/preload-quick-settings.js        |    8 +
 {ui-electron => app/electron/main}/preload.js      |   45 +-
 app/electron/main/services/backendSpawn.js         |  118 ++
 app/electron/main/services/textInjector.js         |   78 +
 app/electron/main/shared/state.js                  |  192 ++
 app/electron/main/utils/api.js                     |  105 +
 app/electron/main/windows/floatingWindow.js        |  162 ++
 app/electron/main/windows/mainWindow.js            |   93 +
 app/electron/main/windows/quickSettingsWindow.js   |   63 +
 app/electron/main/windows/tray.js                  |  350 ++++
 {ui-electron => app/electron}/package-lock.json    | 1568 ++++++++++++++-
 {ui-electron => app/electron}/package.json         |   31 +-
 app/electron/quick-settings.html                   |  319 +++
 .../electron}/scripts/build-frontend.js            |    0
 {ui-electron => app/electron}/scripts/dev.js       |    0
 app/stt/__init__.py                                |   37 +-
 app/stt/chunker.py                                 |    9 +-
 app/stt/dictation_cleanup.py                       |  145 ++
 app/stt/engine.py                                  |   61 +-
 app/stt/fast_chunker.py                            |   39 +-
 app/stt/fast_engine.py                             |  955 +++------
 app/stt/quality.py                                 |  323 +--
 app/ui/README.md                                   |   50 +
 docs/ARCHITECTURE_PLAN.md                          | 1721 ----------------
 docs/api/endpoints.md                              |  261 +++
 docs/{ => deployment}/DEPLOYMENT.md                |   32 +-
 docs/{ => operations}/OPERATIONS.md                |   12 +-
 docs/operations/TESTING.md                         |  470 +++++
 AGENTS.md => docs/project/AGENTS.md                |    4 +-
 docs/project/CHECKLIST.md                          |  344 ++++
 package.json                                       |  260 ++-
 pyproject.toml                                     |   33 +
 requirements.txt                                   |    3 +
 scripts/README.md                                  |  112 --
 scripts/check_cuda.py                              |  373 ----
 scripts/install_pytorch_cuda.ps1                   |  181 --
 test_audio_capture.py                              |  216 --
 tests/conftest.py                                  |  820 +++++++-
 tests/test_dictation_cleanup.py                    |   62 +
 tests/test_fixes.py                                |  391 ++++
 tests/test_model_catalog.py                        |   44 +
 tests/test_settings_manager.py                     |   98 +
 ui-electron/frontend/package.json                  |   33 -
 .../frontend/src/components/ActivityFeed.tsx       |   78 -
 .../frontend/src/components/MainContent.tsx        |  431 ----
 .../frontend/src/components/SettingsPanel.tsx      | 1703 ----------------
 ui-electron/main.js                                | 1101 -----------
 ui-electron/src/main/main.js                       |  107 -
 ui-electron/src/main/preload.js                    |    7 -
 125 files changed, 21940 insertions(+), 9418 deletions(-)
```

## Untracked Files

```text
app/api/refiner_service.py
app/api/settings_sync.py
app/api/websocket_server.py
app/audio/audio_processing.py
app/audio/pipeline_base.py
app/audio/pipeline_factory.py
app/audio/system_pipeline.py
app/audio/vad_optimized.py
app/audio/wispr_pipeline.py
app/config/generate_ts.py
app/core/error_handler.py
app/core/hotkey_session.py
app/core/metrics.py
app/core/mode_manager.py
app/core/modes.py
app/core/performance_monitor.py
app/core/recovery_strategies.py
app/core/system_session.py
app/core/tests/test_metrics.py
app/electron/frontend/.github/workflows/tests.yml
app/electron/frontend/.nycrc.json
app/electron/frontend/src/components/AudioVisualizer.test.tsx
app/electron/frontend/src/components/AudioVisualizer.tsx
app/electron/frontend/src/components/HotkeySettings.test.tsx
app/electron/frontend/src/components/ModeSelector.test.tsx
app/electron/frontend/src/components/ModeSelector.tsx
app/electron/frontend/src/components/ModeSettings.test.tsx
app/electron/frontend/src/components/ModeSettings.tsx
app/electron/frontend/src/components/PartialText.test.tsx
app/electron/frontend/src/components/PartialText.tsx
app/electron/frontend/src/components/TranscriptionStream.tsx
app/electron/frontend/src/components/__tests__/ActivityFeed.test.tsx
app/electron/frontend/src/components/__tests__/App.test.tsx
app/electron/frontend/src/components/__tests__/FloatingWindow.test.tsx
app/electron/frontend/src/components/__tests__/SettingsPanel.test.tsx
app/electron/frontend/src/components/__tests__/Sidebar.test.tsx
app/electron/frontend/src/components/settings/HardwareProfileDisplay.tsx
app/electron/frontend/src/components/settings/HotkeyRecorder.tsx
app/electron/frontend/src/components/settings/ModelComponents.tsx
app/electron/frontend/src/components/settings/SectionHeader.tsx
app/electron/frontend/src/components/settings/SettingCard.tsx
app/electron/frontend/src/components/settings/__tests__/HotkeyRecorder.test.tsx
app/electron/frontend/src/components/settings/__tests__/SettingCard.test.tsx
app/electron/frontend/src/components/settings/categories.ts
app/electron/frontend/src/components/settings/controls/NumberInput.tsx
app/electron/frontend/src/components/settings/controls/Select.tsx
app/electron/frontend/src/components/settings/controls/Slider.tsx
app/electron/frontend/src/components/settings/controls/Toggle.tsx
app/electron/frontend/src/components/settings/controls/index.ts
app/electron/frontend/src/components/settings/index.ts
app/electron/frontend/src/components/settings/presets.ts
app/electron/frontend/src/components/settings/sections/AdvancedSection.tsx
app/electron/frontend/src/components/settings/sections/AudioSection.tsx
app/electron/frontend/src/components/settings/sections/GeneralSection.tsx
app/electron/frontend/src/components/settings/sections/HotkeySection.tsx
app/electron/frontend/src/components/settings/sections/ModelSection.tsx
app/electron/frontend/src/components/settings/sections/TranscriptionSection.tsx
app/electron/frontend/src/components/settings/sections/index.ts
app/electron/frontend/src/components/settings/types.ts
app/electron/frontend/src/components/settings/utils.ts
app/electron/frontend/src/config/generated/constants.ts
app/electron/frontend/src/config/generated/index.ts
app/electron/frontend/src/config/generated/settings.ts
app/electron/frontend/src/config/generated/text.ts
app/electron/frontend/src/config/index.ts
app/electron/frontend/src/context/SettingsContext.tsx
app/electron/frontend/src/hooks/__tests__/useEventSource.test.ts
app/electron/frontend/src/hooks/__tests__/useHotkey.test.ts
app/electron/frontend/src/hooks/__tests__/useHotkey.test.tsx
app/electron/frontend/src/hooks/__tests__/useSettingsSync.test.ts
app/electron/frontend/src/hooks/useSettingsSync.ts
app/electron/frontend/src/hooks/useWebSocket.test.ts
app/electron/frontend/src/hooks/useWebSocket.ts
app/electron/frontend/src/lib/sessionReducer.test.ts
app/electron/frontend/src/lib/settingsApi.test.ts
app/electron/frontend/src/lib/settingsApi.ts
app/electron/frontend/src/test/README.md
app/electron/frontend/src/test/factories.ts
app/electron/frontend/src/test/index.ts
app/electron/frontend/src/test/integration/flows.test.tsx
app/electron/frontend/src/test/integration/websocket.test.tsx
app/electron/frontend/src/test/setup.ts
app/electron/frontend/src/test/utils.ts
app/electron/frontend/test-results/junit.xml
app/electron/main/windows/trayUtils.js
app/stt/fast_whisper_backend.py
app/stt/model_pool.py
app/stt/streaming_engine.py
docs/ARCHITECTURE.md
docs/OPTIMIZATION_SUMMARY.md
docs/README.md
docs/architecture/OPTIMIZATION_ROADMAP.md
docs/architecture/architecture-plan.md
docs/architecture/feature-inventory.md
docs/architecture/implementation-summary.md
docs/audits/performance-audit.md
docs/audits/security-audit.md
docs/operations/fixes-summary.md
docs/operations/verification-checklist.md
docs/project/completion-report.md
docs/project/project-structure.md
docs/project/settings-refactor-summary.md
e2e/conftest.py
e2e/test_hotkey_mode.py
e2e/test_system_mode.py
pnpm-lock.yaml
pytest.ini
reports/changes-since-last-commit.md
reports/tree.txt
scripts/build.py
scripts/generate-changes-since-last-commit.cjs
scripts/generate-tree.cjs
scripts/validate.py
tests/README.md
tests/integration/__init__.py
tests/integration/test_api_endpoints.py
tests/integration/test_file_io.py
tests/integration/test_serialization.py
tests/integration/test_websocket.py
tests/performance/__init__.py
tests/performance/test_concurrency.py
tests/performance/test_latency.py
tests/performance/test_memory.py
tests/performance/test_throughput.py
tests/test_audio_pipelines.py
tests/test_error_handling.py
tests/test_hotkey_session.py
tests/test_mode_manager.py
tests/test_refiner_service.py
tests/test_system_session.py
tests/test_vad_optimized.py
tests/unit/__init__.py
tests/unit/test_audio_pipeline.py
tests/unit/test_error_handler.py
tests/unit/test_session_handler.py
tests/unit/test_settings_manager.py
tests/unit/test_system_pipeline.py
tests/unit/test_transcription_engine.py
tests/unit/test_vad.py
tools/README.md
tools/ci/verify-fixes.py
tools/diagnostics/check-audio.py
tools/diagnostics/check-system.py
tools/maintenance/cleanup-logs.py
tools/runner.py
tools/setup/install-ffmpeg.ps1
tools/setup/install-pytorch-cuda.ps1
```
