---

title: Contributing to Documentation
audience: contributors
last_verified: 2026-03-15
source_of_truth:
  - docs/
  - AGENTS.md
---

# Contributing to Documentation

This guide covers how to contribute to the OpenWispr documentation.

## Quick Reference

| Topic | Location |
|-------|----------|
| General Contributing Guidelines | https://github.com/Harshit-Dhyani/openwispr/blob/main/CONTRIBUTING.md |
| Agent & Developer Guidance | https://github.com/Harshit-Dhyani/openwispr/blob/main/AGENTS.md |
| Documentation Style | [../_style.md](../_style.md) |
| Testing Documentation | [./testing.md](./testing.md) |

## Documentation Structure

```
docs/
├── README.md           # This hub
├── _style.md           # Style guide and conventions
├── troubleshooting.md  # User troubleshooting
├── engineering/        # Technical documentation
├── api/                # API reference
├── reference/         # Feature and config reference
└── project/            # Project management docs
```

## Building Docs

```powershell
# Preview locally
mkdocs serve

# Build for production
mkdocs build

# Verify links
mkdocs build 2>&1 | Select-String "WARNING"
```

## Adding New Documentation

1. Create markdown file in appropriate folder
2. Add required frontmatter (title, audience, last_verified, source_of_truth)
3. Update mkdocs.yml nav section if it's a main page
4. Add link from this hub (docs/README.md)

## Style Guidelines

See [Documentation Style Guide](../_style.md) for:
- Frontmatter requirements
- Markdown conventions
- Admonition usage
- Table formatting
