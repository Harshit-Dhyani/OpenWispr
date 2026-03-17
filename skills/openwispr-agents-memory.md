---
name: openwispr-agents-memory
description: Use when a verified OpenWispr bug, regression, security issue, or unsafe pattern should become a permanent prevention rule in AGENTS.md.
---

# OpenWispr AGENTS Memory

Use this skill only after verifying a real issue.

## Entry Template (Required)

Every new `AGENTS.md` prevention entry must include exactly:

- What went wrong
- Why it happened
- Detect earlier
- Prevention rule

## Minimal Workflow

1. Confirm the issue is real (not hypothesis) via code, test, logs, or reproducible behavior.
2. Verify the issue is not already captured by an existing AGENTS rule.
3. Add one concise entry tied to the specific failure mode.
4. Link the rule to the changed files/flow in the summary for traceability.

## Rules

- Add only specific, actionable rules.
- Do not add generic process advice.
- Keep AGENTS short; dedupe while adding new entries.
- If issue is unverified, do not add a prevention rule.
