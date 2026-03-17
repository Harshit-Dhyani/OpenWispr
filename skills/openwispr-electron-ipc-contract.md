# OpenWispr Electron IPC Contract

## Purpose
Verify that Electron IPC contracts between main and renderer processes are properly defined and maintained.

## When to Use
- When adding new IPC channels
- When modifying existing IPC handlers
- When changing preload scripts
- When debugging IPC communication issues

## When NOT to Use
- For backend-only changes
- For frontend UI changes that don't involve IPC
- For settings-only changes

## Discovery Steps
1. Check preload script for IPC definitions: `app/electron/preload.js`
2. Check main process IPC handlers in `app/electron/`
3. Check renderer IPC usage in `app/electron/frontend/src/`
4. Verify channel names match between preload and main
5. Check for IPC validation at transport boundary

## Verification Requirements
- All IPC channels must be defined in preload
- Main process handlers must validate input
- Renderer must use correct channel names
- Type-safe IPC contracts where possible
- Never expose privileged capabilities beyond preload contract

## Common Failure Patterns
- Adding IPC handlers without preload definitions
- Mismatched channel names between main and renderer
- Missing input validation in handlers
- Exposing too many capabilities in preload
- Not updating both producer and consumer when changing contracts

## Safe Edit Rules
- Always update both IPC producer and consumer
- Validate input at handler, not just UI
- Keep preload contract minimal
- Use channel naming conventions: `<domain>:<action>`
- Run Electron tests after IPC changes
- Verify no breaking changes to existing IPC contracts
