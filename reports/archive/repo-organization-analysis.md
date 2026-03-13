# Repository Organization Analysis - OpenWispr

## 1. CURRENT STRUCTURE DIAGNOSIS

### Patterns Currently in Use

#### Test Organization (MIXED - 4 different patterns)
| Pattern | Location | Examples |
|---------|----------|----------|
| **Colocated with source** | `lib/`, `components/` root | `useWebSocket.test.ts`, `HotkeySettings.test.tsx`, `ModeSelector.test.tsx` |
| **Local `__tests__` folder** | `hooks/__tests__/`, `components/__tests__/`, `pages/__tests__/` | `useHotkey.test.tsx`, `App.test.tsx` |
| **Centralized** | `tests/` (root) | Python backend tests |
| **Integration subfolder** | `test/integration/`, `test/performance/` | `flows.test.tsx`, `websocket.test.tsx` |

#### Wrapper/Re-export Files (IDENTIFIED 7 wrappers)
| Wrapper Path | Re-exports From | Size |
|--------------|-----------------|------|
| `components/pages/HomePage.tsx` | `../../pages/HomePage` | 62 bytes |
| `components/pages/DictionaryPage.tsx` | `../../pages/DictionaryPage` | 62 bytes |
| `components/pages/SnippetsPage.tsx` | `../../pages/SnippetsPage` | 58 bytes |
| `components/pages/FeaturePageShell.tsx` | `../../pages/FeaturePageShell` | 66 bytes |
| `lib/settingsApi.ts` | `../api/settings` | 32 bytes |
| `lib/settingsMigration.ts` | `../config/settingsMigration` | 44 bytes |
| `lib/settingsSchema.ts` | `../config/settingsSchema` | 41 bytes |
| `components/HotkeySettings.tsx` | `./settings/HotkeySettings` | 54 bytes |
| `electron/main/preload.js` | `./preload/main` | 1 line |
| `electron/main/preload-floating.js` | `./preload/floating` | 1 line |
| `electron/main/preload-quick-settings.js` | `./preload/quickSettings` | 1 line |

### What's Working

1. **Backend (Python) structure is clean**: Clear separation by domain (`api/`, `audio/`, `config/`, `core/`, `stt/`, `storage/`, `stem/`, `ui/`)
2. **Centralized test folders for Python**: Good organization with `tests/unit/`, `tests/integration/`, `tests/performance/`, `tests/support/`
3. **Generated files are segregated**: `config/generated/` clearly separates auto-generated from handwritten code
4. **Electron main process has logical subdirectories**: `ipc/`, `services/`, `windows/`, `shared/`, `preload/`

### What's Confusing (Navigation Tax)

1. **Frontend test discovery is fragmented**:
   - Can't predict whether a test is in `__tests__/` or colocated
   - Example: `useHotkey` has tests in BOTH `hooks/__tests__/` and `hooks/` root
   - `HotkeySettings` has tests in 3 locations: `components/`, `components/settings/`, and there are even `.ts` and `.tsx` versions

2. **Wrapper files add noise without value**:
   - The `components/pages/*` wrappers exist only to create a second import path
   - Developers don't know which path to use
   - No clear ownership of the "real" vs "wrapper" file

3. **Duplicate import paths**:
   - Can import settings from both `lib/settingsSchema` AND `config/settingsSchema`
   - Can import pages from both `pages/` AND `components/pages/`
   - This creates confusion about what's canonical

4. **Inconsistent folder hierarchy**:
   - `components/settings/` is a subfolder (reasonable)
   - But pages exist at TWO levels: `pages/` AND `components/pages/`
   - `lib` mixes pure utilities with re-exports

5. **Electron main has wrapper proliferation**:
   - Root `preload.js`, `preload-floating.js`, `preload-quick-settings.js` are all one-liner re-exports
   - This pattern emerged during restructuring but is now just noise

### Where Tests Are Hard to Find

| Area | Current State | Discovery Difficulty |
|------|---------------|---------------------|
| Frontend hooks | Mixed `__tests__` and colocated | Hard - need to check 2 places |
| Frontend components | Mixed `__tests__` and colocated | Hard - need to check 2 places |
| Frontend pages | Both patterns used | Moderate |
| Electron main | Colocated only | Easy |
| Python backend | Centralized only | Easy |

---

## 2. TEST ORGANIZATION VERDICT

### Answer: **Option D - Hybrid Model**

For THIS repo, a hybrid approach is correct because:

**The repo has two very different codebases:**
- **Python backend**: Already well-organized with centralized tests. Keep as-is.
- **Electron/React frontend**: Has mixed patterns that need standardization.

**Backend (Python) - Keep Centralized:**
- Tests are already well-structured in `tests/unit/`, `tests/integration/`, `tests/performance/`
- The domain is stable and tests don't need frequent iteration alongside source
- No changes needed

**Frontend (React) - Adopt Local `__tests__` Folders:**

Rationale:
1. **Colocated tests cause import confusion**: With many re-export wrappers, tests end up in confusing locations
2. **`__tests__` is explicit and discoverable**: `hooks/__tests__/useHotkey.test.tsx` is unambiguous
3. **Matches what developers expect**: Most React/Vitest projects use this pattern
4. **Reduces duplicate test files**: The pattern prevents having both `Foo.test.ts` and `Foo.test.tsx` for the same component

**What NOT to do:**
- Don't create wrappers that re-export tests
- Don't mix patterns within the same directory

---

## 3. TARGET FOLDER STRUCTURE

### Recommended Structure

```
app/electron/frontend/src/
├── components/           # UI components (keep)
│   ├── __tests__/       # ALL component tests go here
│   ├── settings/       # Settings-related components
│   │   └── __tests__/  # Settings component tests
│   └── ...
├── pages/               # Page components (canonical location)
│   ├── __tests__/      # Page tests
│   ├── HomePage.tsx
│   ├── DictionaryPage.tsx
│   └── SnippetsPage.tsx
├── hooks/              # Custom hooks
│   ├── __tests__/      # ALL hook tests go here
│   ├── useHotkey.ts
│   ├── useWebSocket.ts
│   └── useEventSource.ts
├── lib/                # Pure utilities ONLY - NO re-exports
│   ├── sessionReducer.ts
│   ├── modelRegistry.ts
│   └── constants.ts
├── api/                # API client code
│   └── settings.ts
├── config/             # Configuration (canonical location)
│   ├── settingsSchema.ts   # REAL file
│   ├── settingsMigration.ts # REAL file
│   └── generated/
├── context/            # React contexts
├── types/             # TypeScript types
└── test/              # ONLY for test utilities, setup, integration
    ├── setup.ts
    ├── factories.ts
    ├── utils.ts
    └── integration/    # Integration tests only
```

### Ownership Rules

| Path | Ownership | Rule |
|------|-----------|------|
| `pages/` | Pages | Canonical source - no wrappers |
| `components/` | UI | Canonical source |
| `lib/` | Utilities | Pure functions only, no re-exports |
| `config/` | Settings/config | Canonical source |
| `api/` | API clients | Canonical source |
| `hooks/` | React hooks | Canonical source |
| `*/__tests__/` | Tests | All tests for that domain |
| `test/` | Test utilities | Only fixtures, setup, integration |

### Folders That Should Be Feature-First

The current `components/pages/` wrapper pattern is wrong. The correct approach:

**Keep pages flat at `pages/` (already correct), remove `components/pages/` entirely.**

For future growth, if features become large enough:
```
features/
  ├── transcript/
  │   ├── components/
  │   ├── hooks/
  │   └── __tests__/
  ├── settings/
  │   ├── components/
  │   ├── hooks/
  │   └── __tests__/
  └── ...
```

But the current scale doesn't warrant this. Stay flat.

---

## 4. MIGRATION PLAN

### Phase 1: Easy Wins (Low Risk)

**1.1 Remove wrapper re-export files (do NOT delete the real files)**

```bash
# Frontend wrappers to remove
rm app/electron/frontend/src/components/pages/HomePage.tsx
rm app/electron/frontend/src/components/pages/DictionaryPage.tsx
rm app/electron/frontend/src/components/pages/SnippetsPage.tsx
rm app/electron/frontend/src/components/pages/FeaturePageShell.tsx
rm app/electron/frontend/src/components/pages/__tests__

# lib re-exports to remove (these add no value)
rm app/electron/frontend/src/lib/settingsApi.ts
rm app/electron/frontend/src/lib/settingsMigration.ts
rm app/electron/frontend/src/lib/settingsSchema.ts

# Update imports in App.tsx to use canonical paths
# (will be covered in migration step)
```

**1.2 Remove duplicate HotkeySettings wrapper**

```bash
rm app/electron/frontend/src/components/HotkeySettings.tsx
# Keep: components/settings/HotkeySettings.tsx as canonical
# Keep: components/settings/HotkeySettings.test.tsx as test
```

**1.3 Remove Electron main wrappers**

```bash
# These one-liners add no value
rm app/electron/main/preload.js
rm app/electron/main/preload-floating.js  
rm app/electron/main/preload-quick-settings.js

# Update package.json or build config to point to preload/main.js directly
```

### Phase 2: Standardization

**2.1 Consolidate frontend test locations to `__tests__` folders**

Move tests that are currently colocated into `__tests__` folders:

```bash
# For hooks - move colocated tests to __tests__/
mv app/electron/frontend/src/hooks/useWebSocket.test.ts \
   app/electron/frontend/src/hooks/__tests__/

# For components - move to __tests__/
mv app/electron/frontend/src/components/HotkeySettings.test.tsx \
   app/electron/frontend/src/components/__tests__/
mv app/electron/frontend/src/components/ModeSelector.test.tsx \
   app/electron/frontend/src/components/__tests__/
mv app/electron/frontend/src/components/ModeSettings.test.tsx \
   app/electron/frontend/src/components/__tests__/
mv app/electron/frontend/src/components/AudioVisualizer.test.tsx \
   app/electron/frontend/src/components/__tests__/
mv app/electron/frontend/src/components/PartialText.test.tsx \
   app/electron/frontend/src/components/__tests__/
```

**2.2 Remove duplicate test files**

```bash
# Remove the .ts version, keep .tsx
rm app/electron/frontend/src/hooks/__tests__/useHotkey.test.ts
# Keep: useHotkey.test.tsx
```

### Phase 3: Structural Cleanup

**3.1 Clean up lib/ folder**

After removing wrappers, `lib/` should contain ONLY pure utilities. Verify no re-exports remain.

**3.2 Update all import statements**

Update App.tsx and other files to use canonical import paths:

```typescript
// BEFORE (uses wrapper)
import { DEFAULT_SETTINGS } from './lib/settingsSchema';

// AFTER (canonical path)
import { DEFAULT_SETTINGS } from './config/settingsSchema';
```

### Phase 4: Deeper Reorganization (Only If Needed)

Only pursue if Phase 1-3 don't sufficiently reduce confusion:

- Consider feature-first layout if pages/ grows significantly
- Evaluate whether `components/settings/` should move under features
- Consider splitting large lib/ into domain-specific modules

---

## 5. FILE/FOLDER RULES

### Explicit Rules

**Where unit tests go:**
- Frontend: `*/__tests__/` folder for that domain
- Backend: `tests/unit/` (already correct)

**Where integration tests go:**
- Frontend: `test/integration/`
- Backend: `tests/integration/`

**When to use `__tests__`:**
- ALWAYS for frontend code (components, hooks, pages)
- NEVER create colocated `.test.*` files in frontend

**When to colocate tests:**
- ONLY for Electron main process JavaScript files (current pattern works)
- ONLY for Python backend (already centralized)

**When wrapper files are allowed:**
- NEVER for the purpose of creating alternate import paths
- ONLY as compatibility shims when transitioning APIs (with deprecation timeline)
- NEVER for tests

**When files belong in `shared`:**
- Code used by both main process AND renderer
- Constants, types used across boundaries

**When files belong in a feature folder:**
- When a feature has >5 related components
- When a feature has its own state/logic that doesn't fit elsewhere
- Current repo scale doesn't warrant this yet

---

## 6. DO NOT DO LIST

### Restructuring Mistakes to Avoid

1. **Don't delete real files when removing wrappers** - Verify the wrapper re-exports another file, don't delete that other file

2. **Don't create new wrapper files** - The whole point is to remove these

3. **Don't mix test patterns** - Pick one pattern per directory and stick to it

4. **Don't move tests AND change import paths in the same PR** - Too hard to review; split into separate changes

5. **Don't restructure the backend** - Python tests are already well-organized

6. **Don't create feature folders prematurely** - Current flat structure works; only add features/ if truly needed

7. **Don't forget to update imports** - After removing wrappers, update all import statements

8. **Don't delete __tests__ folders that have real tests** - Verify what's in them before removing

---

## 7. OPTIONAL SAFE REFACTOR STARTERS

### First Batch (Minimal Risk)

These changes have zero behavioral impact and clear up confusion:

```bash
# 1. Remove the components/pages wrapper folder entirely
# (These are pure re-exports with no tests in them)
rm -rf app/electron/frontend/src/components/pages/

# 2. Remove lib/ re-export wrappers
rm app/electron/frontend/src/lib/settingsApi.ts
rm app/electron/frontend/src/lib/settingsMigration.ts  
rm app/electron/frontend/src/lib/settingsSchema.ts

# 3. Remove duplicate HotkeySettings wrapper
rm app/electron/frontend/src/components/HotkeySettings.tsx
```

### Second Batch (Update imports after wrappers removed)

```typescript
// In App.tsx, change these imports:
// FROM: import { DEFAULT_SETTINGS } from './lib/settingsSchema';
// TO:   import { DEFAULT_SETTINGS } from './config/settingsSchema';

// FROM: import { DictionaryPage } from './components/pages/DictionaryPage';
// TO:   import { DictionaryPage } from './pages/DictionaryPage';

// Similar updates for other wrapper imports
```

### Third Batch (Test consolidation)

```bash
# Move colocated frontend tests to __tests__ folders
# This is safe because Vitest finds tests anywhere
mv app/electron/frontend/src/hooks/useWebSocket.test.ts \
   app/electron/frontend/src/hooks/__tests__/
```

---

## Summary

The repo's confusion comes from **inconsistent test organization** and **unnecessary wrapper files** that create multiple import paths for the same module. The fix is:

1. **Remove all re-export wrappers** (11 files identified)
2. **Standardize on `__tests__` folders** for frontend code
3. **Keep backend as-is** (already well-organized)
4. **Never create alternate import paths** for the same module

This is a high-signal, low-risk cleanup that will immediately reduce navigation tax without breaking any functionality.
