---
title: Contributing to Documentation
audience: developers
last_verified: 2026-03-08
source_of_truth:
  - docs/_style.md
  - tools/ci/verify-docs.py
---

# Contributing to Documentation

Guide for adding and updating documentation in the OpenWispr project.

## How to Update Docs

1. **Edit existing files** directly - most docs are Markdown in `docs/`
2. **Add new files** in the appropriate subdirectory:
   - `docs/api/` - API documentation
   - `docs/architecture/` - Design and architecture docs
   - `docs/audits/` - Security and performance audits
   - `docs/deployment/` - Deployment guides
   - `docs/operations/` - Operations and troubleshooting
   - `docs/project/` - Project structure and setup
   - `docs/reference/` - Feature and configuration references
   - `docs/engineering/` - Engineering and contribution guides
3. **Update inventory** - Add new files to `docs/_inventory.yml`
4. **Run validation** - Execute `python tools/ci/verify-docs.py`
5. **Submit PR** - Include documentation changes in your pull request

## Required Frontmatter

Every documentation file must include YAML frontmatter at the top:

```yaml
---
title: "Document Title"
audience: developers|operators|security|all
last_verified: "2026-03-08"
source_of_truth:
  - path/to/file.py
  - path/to/other.py:10-50
---
```

### Field Descriptions

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Human-readable document title |
| `audience` | Yes | Target reader: `developers`, `operators`, `security`, or `all` |
| `last_verified` | Yes | Date this doc was last verified accurate (YYYY-MM-DD) |
| `source_of_truth` | Yes | Paths to authoritative code/config files |

## Evidence Requirements

When documenting features or behavior:

1. **Link to source code** - Use `path/file.py::ClassName` or `path/file.py:123-456` format
2. **Include examples** - Show real configuration values, API responses, or CLI commands
3. **Reference related docs** - Cross-link using relative paths (e.g., `[Feature Guide](../reference/features.md)`)
4. **Cite test files** - When behavior is tested, reference the test: `tests/test_feature.py`

## Review Checklist

Before submitting documentation changes:

- [ ] Frontmatter includes all required fields with valid values
- [ ] Title in frontmatter matches H1 heading in document
- [ ] Code references use correct citation format
- [ ] Cross-links to other docs are relative and valid
- [ ] Last verified date is current
- [ ] File is added to `docs/_inventory.yml`
- [ ] `python tools/ci/verify-docs.py` passes with no errors
- [ ] Terminology is consistent with other docs (see below)

## Terminology Standards

Use these terms consistently across all documentation:

| Term | Meaning | Notes |
|------|---------|-------|
| **Dictation** | Spoken input that gets transcribed | Use for the act of speaking |
| **Session** | A recording/transcription period | Has start, stop, and export lifecycle |
| **Segment** | One chunk of transcript output | Smallest unit of transcription result |
| **Utterance** | A complete spoken phrase | May span multiple segments |
| **Hotkey Mode** | Push-to-talk microphone transcription | Also called "Wispr Mode" in code |
| **System Mode** | System audio/loopback transcription | For videos, meetings, podcasts |
| **ASR** | Automatic Speech Recognition | The Whisper transcription models |
| **Refiner** | LLM post-processing | Optional text cleanup/enhancement |

## Code Citation Format

Reference source code using these formats:

```markdown
# Symbol reference (class, function)
app/core/settings_manager.py::SettingsManager

# Method reference
app/api/service.py::TranscriptionService.transcribe

# Line range reference
app/config/settings.py:45-120

# Single line reference
app/core/error_handler.py:331

# File reference (use sparingly)
app/audio/capture.py
```

## Cross-Linking Guidelines

Link to related documentation using relative paths:

```markdown
# Link to doc in same directory
[API Reference](./testing.md)

# Link to doc in parent directory
[Troubleshooting](../troubleshooting.md)

# Link to doc in sibling directory
[Operations Guide](../operations/OPERATIONS.md)

# Link with anchor
[Settings](../reference/config.md#environment-variables)
```

## Running Validation

Always run the documentation validator before submitting:

```powershell
# Run validation
python tools/ci/verify-docs.py

# Expected output on success:
# ============================================================
# Documentation Quality Gate
# ============================================================
#
# [1/3] Validating frontmatter...
#   [PASS] All X files have valid frontmatter
#
# [2/3] Checking inventory sync...
#   [PASS] Inventory is synchronized
#
# [3/3] Validating internal links...
#   [PASS] All internal links are valid
#
# ============================================================
# SUCCESS: All documentation checks passed
# ============================================================
```

## Inventory Format

When adding to `docs/_inventory.yml`:

```yaml
- path: relative/path/from/docs.md
  title: Human Readable Title
  owner: docs/ux
  audience: developers|operators|security|all
  last_verified: 2026-03-08
  review_cadence: monthly|quarterly
  source_of_truth:
    - path/to/source.py
    - another/path.py:10-50
  critical: true|false
```

## Review Cadence

Keep documentation accurate by reviewing on schedule:

| Document Type | Review Frequency |
|--------------|------------------|
| API reference | Monthly |
| Configuration | Monthly |
| Troubleshooting | Monthly |
| Operations | Monthly |
| Architecture | Quarterly |
| Audit reports | Quarterly |
| Project structure | Quarterly |

## Related Documents

- [Documentation Style Guide](../_style.md) - Complete style reference
- [Contributing Guide](../../CONTRIBUTING.md) - General contribution guidelines
