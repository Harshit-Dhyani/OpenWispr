# OpenWispr Audio Pipeline Audit

## Purpose
Detect and report audio pipeline duplication across the codebase.

## When to Use
- Before adding new audio processing code
- When investigating audio-related bugs
- When refactoring audio modules
- When merging branches that touch audio code

## When NOT to Use
- For unrelated UI changes
- When audio pipeline is known to be isolated
- For settings-only changes that don't affect audio flow

## Discovery Steps
1. Search for audio pipeline directories: `Get-ChildItem -Path app/audio -Recurse -Filter "*.py" | Select-Object FullName`
2. Check for duplicate pipeline files outside `app/audio/pipelines/`
3. Look for audio imports in non-pipeline directories: `Get-ChildItem -Path app -Recurse -Filter "*.py" | Select-String -Pattern "from app.audio" | Where-Object { $_.Path -notmatch "app/audio/pipelines" }`
4. Verify single source of truth in `app/audio/pipelines/`
5. Check for old pipeline locations that should be shims

## Verification Requirements
- All audio pipeline code must be in `app/audio/pipelines/` only
- Any backward-compatible shims must be explicitly marked
- No duplicate audio processing logic in multiple locations

## Common Failure Patterns
- Creating new audio pipeline files outside `app/audio/pipelines/`
- Copying audio logic to "temporary" locations
- Not converting old locations to shims after moving to canonical location
- Multiple model download managers or pipeline factories

## Safe Edit Rules
- Always check if canonical location already exists before creating new files
- If moving pipeline code, convert old location to backward-compatible shim
- Verify imports resolve correctly after any move
- Run audio-related tests after changes
