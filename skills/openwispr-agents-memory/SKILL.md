---
name: openwispr-agents-memory
description: Use when a verified OpenWispr bug, regression, security issue, or unsafe pattern should become a permanent prevention rule in AGENTS.md.
---

# OpenWispr AGENTS Memory

Use this skill only after verifying a real issue.

## Goal

Turn a concrete failure into a short regression-prevention rule in `AGENTS.md`.

## Required Entry Shape

Each new entry must capture:

- what went wrong
- why it happened
- how to detect it earlier
- the prevention rule

## Rules

- Add only specific, actionable rules.
- Do not add broad process notes.
- Keep `AGENTS.md` short.
- Prefer one rule per verified failure mode.
- If the issue is not yet verified, do not add the rule.
