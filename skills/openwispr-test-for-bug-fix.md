# OpenWispr Test for Bug Fix

## Purpose
Generate focused regression tests when fixing bugs.

## When to Use
- When fixing any bug
- When addressing regressions
- When modifying existing functionality

## When NOT to Use
- For purely cosmetic changes
- For documentation updates only
- For adding new features (use feature tests instead)

## Discovery Steps
1. Identify the bug: understand what behavior changed or broke
2. Find existing tests for similar functionality: `find tests -name "*.py" | xargs grep -l "keyword"`
3. Check test patterns in the codebase
4. Identify the component/module being fixed
5. Determine test type: unit, integration, or e2e

## Verification Requirements
- At least one focused regression test for the bug fix
- Test must fail before the fix and pass after
- Test should cover the specific bug scenario, not entire module
- Tests must follow existing test patterns in the codebase

## Common Failure Patterns
- Adding tests to wrong location
- Writing integration tests when unit tests are more appropriate
- Testing too much, making tests fragile
- Not following existing test naming conventions
- Forgetting to run tests after adding

## Safe Edit Rules
- Follow existing test file naming: `test_<module>.py`
- Use pytest fixtures like existing tests
- Keep tests focused and specific to the bug
- Run tests after adding: `pytest tests/ -v`
- Use descriptive test names that explain what is being tested
- For settings changes, check `tests/test_settings_wiring.py` as reference
