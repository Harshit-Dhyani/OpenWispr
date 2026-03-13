# Docs Source-of-Truth Audit - 2026-03-08

## Verification Update - 2026-03-09
- Scope reviewed: docs/report naming, compatibility-sensitive legacy identifiers, and the verified report fixes from this batch.
- Status counts for items verified in this pass: `completed=1`, `invalid=0`, `deferred=1`, `compatibility-retained=1`
- Result: prose references now use `OpenWispr` where safe, while `TRANSCRIPTA_*`, `.transcripta`, and preload globals remain documented as compatibility-sensitive legacy identifiers.

## Summary
Audit of documentation accuracy, source-of-truth alignment, and documentation drift. Found issues with duplicate docs, transitional docs, and naming inconsistencies.

## Scope
- docs/
- docs/_inventory.yml
- app/config/settings.py
- app/core/settings/
- app/api/

## Findings

### P0 - Must Fix

**D0-1: Duplicate Model Documentation**
- Files: docs/architecture/MODEL_SYSTEM.md, docs/engineering/model-runtime.md
- What: Same topic in two locations creating authority conflict
- Why: Users confused about which is authoritative
- Evidence: Both describe model system
- Fix: Keep model-runtime.md, archive MODEL_SYSTEM.md (already done)
- Verify: Check for remaining duplicates

**D0-2: Duplicate Folder Ownership Docs**
- Files: docs/engineering/folder-ownership.md, docs/project/folder-ownership.md
- What: Two versions of same document
- Fix: Keep project/folder-ownership.md (already done)
- Verify: Check docs structure

### P1 - Should Fix

**D1-1: Transitional Docs Not Labeled**
- Files: docs/engineering/restructure-*.md, docs/engineering/settings-source-of-truth.md
- What: Migration docs claim "verified" status
- Why: These are transitional, not stable reference
- Fix: Add status: transitional (already done)
- Verify: Check frontmatter

**D1-2: Settings Docs Contain Bugs**
- Files: docs/engineering/settings.md, docs/reference/config.md
- What: Settings docs describe schema but don't mention known bugs
- Why: Undermines trust
- Fix: Add "Known Issues" section to docs
- Verify: Check settings docs

### P2 - Nice to Have

**D2-1: TRANSCRIPTA Naming Not Acknowledged**
- Files: docs/ (general)
- What: Code uses .transcripta, TRANSCRIPTA_* but docs don't mention
- Fix: Added note in operations.md (already done)
- Verify: Check operations.md

**D2-2: README Overloaded**
- File: README.md (root)
- What: 444 lines with engineering details
- Fix: Trimmed to 56 lines (already done)
- Verify: Check README line count

## Quick Wins
1. Verify duplicate docs archived
2. Check transitional labels present
3. Confirm operations.md has naming note

## Done-When
- [ ] No duplicate docs without deprecation notice
- [ ] All transitional docs labeled
- [ ] Naming conventions documented
