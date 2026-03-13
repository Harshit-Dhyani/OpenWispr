You are working in a real production-style repository for OpenWispr, a local-first desktop transcription app with a Python backend, Electron main process, and React/TypeScript frontend.

Your job is to perform a true discovery-first, whole-project audit and generate or update a small, high-value set of Markdown audit/report files under the root-level `reports/` folder.

Primary goal:
Create practical Markdown audit files that improve the app’s quality, security, performance, maintainability, correctness, and structure without making speculative claims.

Critical instruction:
This is a full-project audit, not a grep-based scan.
You must inspect the repository broadly and deeply.
Do not just search for a few suspicious keywords and stop.
Do not rely on grep-only workflows.
Do not produce shallow reports from partial inspection.
You must read representative files across all major areas of the project and audit each area according to the purpose of its files.

Important constraints:
- Discovery first. Inspect before writing.
- Treat all file paths as hints, not certainties.
- Do not guess architecture or wiring.
- Do not blindly trust existing docs or reports.
- Do not create fluff reports.
- Prefer fewer, stronger reports over many shallow ones.
- Do not modify runtime code unless explicitly required. This task is about generating audit/report Markdown files.
- Write only files inside the root `reports/` folder unless a tiny supporting index update is clearly necessary.
- If a report already exists, update, merge, or supersede it carefully instead of creating noisy duplicates.
- Be honest about uncertainty.
- Distinguish clearly between:
  1. verified issues
  2. likely risks
  3. improvement opportunities
  4. future cleanup ideas

Audit depth requirement:
You must audit the project area by area, not just by keyword.
For each major area, inspect files based on what they are supposed to do.

Examples:
- For API/server files: inspect request handling, validation, serialization, state handling, transport contracts, error handling, and route consistency.
- For settings/config files: inspect defaults, duplication, migration drift, source-of-truth problems, and frontend/backend mismatch.
- For Electron files: inspect preload exposure, IPC boundaries, event naming, state flow, and legacy/new path drift.
- For frontend files: inspect duplicated logic, stale contracts, settings drift, weak typing, and dead or overlapping components.
- For audio/STT/runtime files: inspect queueing, fallback behavior, performance assumptions, model routing, and error recovery.
- For tests: inspect missing coverage areas, contract drift, weak assertions, and areas with likely under-tested critical behavior.
- For docs/reports: inspect duplication, contradiction, overstated certainty, stale architecture claims, and source-of-truth drift.

You are not required to read every single line of every single file in the repository, but you must inspect enough files across every major subsystem to make the audit meaningfully comprehensive.
Do not skip entire subsystems.
Do not stop at existing reports.
Do not treat old audit files as ground truth.

Repo context to inspect:
- README.md
- docs/
- reports/
- app/api/
- app/audio/
- app/config/
- app/core/
- app/electron/
- app/stt/
- app/storage/
- tests/
- e2e/
- tools/
- scripts/
- package.json
- pyproject.toml
- AGENTS.md
- CONTRIBUTING.md

Required audit behavior:
1. Discover the repo structure first.
2. Inspect existing reports in `reports/` to understand what already exists.
3. Audit each major subsystem of the repo based on its purpose.
4. Compare code, docs, reports, and structure to identify contradictions and gaps.
5. Update existing reports where appropriate.
6. Create new reports only where genuinely needed.
7. Avoid duplication and shallow restatement.
8. Make the final set of reports non-redundant, specific, and actionable.

Audit focus:
Generate or update Markdown reports that help improve the app in areas like:
- security vulnerabilities and risky patterns
- correctness bugs and likely defects
- performance bottlenecks and optimization opportunities
- architectural / folder-structure problems
- documentation drift / source-of-truth issues
- settings/configuration inconsistencies
- duplicated code or overlapping modules
- reliability / error-handling / recovery gaps
- testing gaps and weak coverage areas
- release-readiness / operator-readiness issues

Recommended report set:
Use the existing naming pattern in `reports/` if one already exists.
Otherwise prefer a clear, date-based naming pattern such as:
- `reports/security-audit-YYYY-MM-DD.md`
- `reports/performance-optimization-YYYY-MM-DD.md`
- `reports/architecture-structure-audit-YYYY-MM-DD.md`
- `reports/settings-config-audit-YYYY-MM-DD.md`
- `reports/testing-gap-analysis-YYYY-MM-DD.md`
- `reports/docs-source-of-truth-audit-YYYY-MM-DD.md`
- `reports/master-improvement-roadmap-YYYY-MM-DD.md`

If equivalent reports already exist:
- update them if they are still the right home
- merge overlapping reports if needed
- supersede older reports only when clearly justified
- avoid creating duplicates that say almost the same thing

For each report:
- Start with a short summary
- Include scope
- Include evidence-based findings
- Separate verified findings from hypotheses / needs-verification items
- Group findings by severity:
  - P0 must-fix
  - P1 should-fix
  - P2 nice-to-have
- For each finding include:
  - what is wrong
  - why it matters
  - evidence (exact file paths, symbols, or observed duplication/contract drift)
  - smallest safe fix
  - verification step
- End with:
  - quick wins
  - deeper follow-up work
  - done-when criteria

Required master roadmap file:
Create or update one final roadmap file that:
- summarizes all reports
- deduplicates overlapping recommendations
- orders fixes by impact vs risk
- suggests an execution sequence
- clearly separates:
  - docs-only fixes
  - low-risk code fixes
  - medium-risk refactors
  - high-risk migration work

Rules for evidence:
- Use exact file paths wherever possible
- Do not invent line numbers if unavailable
- Do not claim vulnerabilities or bugs without basis
- If something looks suspicious but is not confirmed, label it as `needs verification`
- If an existing report made a claim, verify it against current repo reality before repeating it

Rules for style:
- Markdown only
- Concise but substantive
- No filler
- No marketing language
- No fake certainty
- No giant walls of generic advice
- No shallow grep-style observations pretending to be a full audit

Mandatory coverage requirement:
Your audit must cover all major repo areas:
- backend/API
- audio/runtime/STT
- config/settings
- Electron main/preload/IPC
- frontend
- storage/session/history
- tests/e2e
- docs/reports/tooling/scripts

If a subsystem appears lightly reviewed or uncertain, say so explicitly in the final response and in the relevant report.

Required final response:
1. Brief discovery summary
2. Exact files created or updated in `reports/`
3. 1 to 3 bullets per file explaining why it was created or updated
4. Key cross-cutting themes
5. Coverage summary by subsystem
6. Done-when checklist

Success criteria:
- The repo ends up with a useful, grounded set of audit Markdown files in `reports/`
- Existing reports are updated or consolidated when appropriate
- The reports are actionable and non-duplicative
- They help future AI or human contributors improve the app safely
- They reflect actual repo reality, not fantasy architecture
- The audit is broad enough to cover every major subsystem, not just a few grepped keywords
Before writing reports, produce a private audit map of the repo areas you inspected and do not finalize until every major subsystem has been reviewed at least once.