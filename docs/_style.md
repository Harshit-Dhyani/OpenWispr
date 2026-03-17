# Documentation Style Guide

This document defines the required standards for all documentation in this repository.

## Required Frontmatter

Every documentation file must include this YAML frontmatter at the top:

```yaml
---
title: "Document Title"
audience: developers|operators|security|all
last_verified: "2026-03-15"
source_of_truth:
  - path/to/file.py
  - path/to/other.py:10-50
---
```

### Field Descriptions

| Field | Required | Format | Description |
|-------|----------|--------|-------------|
| `title` | Yes | String | Human-readable document title |
| `audience` | Yes | Enum | Target reader: `developers`, `operators`, `security`, or `all` |
| `last_verified` | Yes | YYYY-MM-DD | Date this doc was last verified accurate |
| `source_of_truth` | Yes | List | Paths to code/config files that are authoritative |

## Code Citations

Use these formats when referencing source code:

### Symbol References
```
# Class or function name
app/core/settings_manager.py::SettingsManager

# Method within class
app/api/service.py::TranscriptionService.transcribe
```

### Line Range References
```
# Specific line range
app/config/settings.py:45-120

# Single line
app/core/error_handler.py:331
```

### File References
```
# Entire file (use sparingly)
app/audio/capture.py
```

## Writing Tone

- **Technical**: Use precise terminology. Avoid vague descriptions.
- **Imperative for procedures**: "Run the command", "Set the variable", "Restart the service"
- **Active voice**: "The service validates input" not "Input is validated by the service"
- **Present tense**: "The function returns" not "The function will return"

## Document Structure

1. **Title**: H1 heading matching frontmatter title
2. **Overview**: 2-3 sentence summary of document purpose
3. **Table of Contents**: For docs over 100 lines
4. **Sections**: Logical H2/H3 groupings
5. **Code Examples**: All code blocks must have language tags
6. **Cross-References**: Link to related docs using relative paths

## Link Conventions

```markdown
# Internal document link
[Deployment Guide](./deployment/DEPLOYMENT.md)

# Section anchor
[Troubleshooting](#troubleshooting)

# External link with note
[Whisper Documentation](https://github.com/openai/whisper) (external)
```

## Review Cadence

| Document Type | Review Frequency |
|--------------|------------------|
| API reference | Monthly |
| Configuration | Monthly |
| Troubleshooting | Monthly |
| Architecture | Quarterly |
| Audit reports | Quarterly |
| Project structure | Quarterly |

## Validation

All documentation is validated by `tools/ci/verify-docs.py` in CI.

Run locally:
```bash
python tools/ci/verify-docs.py
```
