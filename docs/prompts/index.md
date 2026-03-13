# OpenWispr Prompts

This directory contains reusable prompts for common development tasks. Each subdirectory serves a specific purpose.

## Structure

```
prompts/
├── audit/              # Comprehensive audit prompts
│   ├── full-repo.md   # Full project audit
│   ├── settings-wiring.md  # Settings flow audit
│   ├── public-repo-readiness.md  # Public release readiness
│   └── security-audit.md  # Security review
├── implementation/    # Implementation task prompts
│   └── bug-fix-template.md  # Bug fix workflow
├── maintenance/      # Maintenance tasks
│   └── deprecation-cleanup.md  # Shim cleanup
├── testing/          # Test creation prompts
│   └── test-generation.md   # Test generation guide
└── release/          # Release preparation
    └── pre-flight.md # Pre-release checklist
```

## When to Use Each Prompt

### Audits
- **full-repo.md** - Run when you need a comprehensive review of the entire codebase
- **settings-wiring.md** - Use when investigating settings-related bugs or migrations
- **public-repo-readiness.md** - Run before making repo public or releasing
- **security-audit.md** - Run when adding new dependencies or IPC handlers

### Implementation
- **bug-fix-template.md** - Follow this template when fixing bugs to ensure proper verification

### Maintenance
- **deprecation-cleanup.md** - Run when auditing old code and planning cleanup

### Testing
- **test-generation.md** - Reference this guide when adding new tests

### Release
- **pre-flight.md** - Run before creating a release to ensure readiness

## Quick Access

To use a prompt, copy its contents and paste into your AI assistant.
