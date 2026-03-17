# Public Documentation Honesty Skill

## Purpose

Ensure all public-facing documentation, marketing materials, and user-facing content accurately reflects the current state of the codebase. Never overclaim features, privacy, performance, or platform support.

Use this skill when:
- Writing or updating user-facing documentation (mkdocs/docs/)
- Updating README.md or project descriptions
- Creating marketing materials or website content
- Documenting feature capabilities
- Making claims about privacy, performance, or platform support

## When NOT to Use

- Internal technical documentation
- Code comments and docstrings
- AGENTS.md and development guidelines
- Debug/logging content

## Rules

1. **Never overclaim support**: Only document features that are verified in current code
2. **Distinguish current vs target**: Clearly state what works now vs what is planned
3. **Privacy claims must be code-verified**: Don't claim privacy without verifying no network calls
4. **Performance claims need measurement**: Don't claim specific latency/throughput without measurement
5. **Platform support must be tested**: Don't claim support for untested platforms
6. **Version accuracy**: Ensure version numbers match actual releases
7. **No placeholder text**: Don't leave TODO/FIXME in public docs

## Discovery Steps

1. Check the actual implementation for the feature being documented
2. Search for network calls, telemetry, external services
3. Look for platform-specific code paths
4. Verify with runtime testing if possible
5. Check AGENTS.md for accuracy requirements

## Verification

- Run the feature if possible
- Search code for claims being made
- Verify no "todo" or "future" language in finished features
- Check that code and docs agree

## Common Failure Patterns

1. **Privacy overclaiming**: Claiming "offline only" when network calls exist
2. **Performance claims**: Stating specific latency without measurements
3. **Platform support**: Claiming cross-platform without testing
4. **Feature creep**: Documenting planned features as shipped
5. **Version drift**: Documentation refers to old versions or unreleased changes
6. **Placeholder text**: Leaving TODO/FIXME in public-facing docs
