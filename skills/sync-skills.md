# Skills Sync Skill

## Purpose

Sync skills from .codex folder to the main skills/ folder for backward compatibility. This ensures older tools that expect skills in the root-level skills/ folder continue to work.

## When to Use

- After creating new skills in .codex/
- Before running tools that expect skills in skills/
- As part of the build/release process

## Implementation

This skill runs the sync command:
```bash
bun run skills sync
```

## How Sync Works

1. Reads all skill folders from `.codex/*/skill.md`
2. Copies each skill.md to `skills/{skill-name}.md`
3. Preserves skill content exactly as-is

## Verification

1. Check that skills/ folder contains all skills from .codex/
2. Run `ls skills/` to verify
3. Test that older tools work with synced skills
