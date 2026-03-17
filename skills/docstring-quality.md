# Docstring Quality Skill

## Purpose

Ensure all code documentation (docstrings) meets AGENTS.md standards - describing what code actually does, not what it should do.

Use this skill when:
- Adding docstrings to new modules, classes, or functions
- Fixing incorrect or outdated docstrings
- Auditing code for missing documentation
- Ensuring docstrings match implementation

## When NOT to Use

- User-facing documentation (use mkdocs/)
- README files
- Configuration files
- Test files (optional)

## Docstring Requirements by Type

### Module Docstrings
Required for:
- `app/stt/**` - all modules
- `app/audio/**` - all modules  
- `app/api/**` - all modules
- `app/core/**` - all modules
- `app/storage/**` - all modules

Must describe:
- Purpose of the module
- Key classes/functions
- Dependencies and collaborators

### Class Docstrings
Required for:
- SessionManager
- LoopbackAudioSource
- WhisperTranscriber
- HistoryDatabase
- AppSettings

Must describe:
- State ownership
- Lifecycle assumptions
- Key methods

### Function Docstrings
Required for:
- Public API functions
- Service methods
- Callback handlers

Must describe:
- What the function does
- Args and Returns
- Edge cases

## Discovery Steps

1. Identify the file/module needing docstrings
2. Check if it's in a required location:
   - `app/stt/**` - all modules need module docstrings
   - `app/audio/**` - all modules need module docstrings
   - `app/api/**` - all modules need module docstrings
   - `app/core/**` - all modules need module docstrings
   - `app/storage/**` - all modules need module docstrings
3. Check for required class docstrings:
   - SessionManager, LoopbackAudioSource, WhisperTranscriber, HistoryDatabase, AppSettings
4. Review existing docstrings in similar files for style reference
5. Verify what the code actually does (not what it should do)

## Rules

1. **Describe actual behavior**: Not what it should do, but what it does
2. **Distinguish current vs target**: If behavior is incomplete, note it
3. **No comments that state the obvious**: Don't explain trivial code
4. **Explain why, not what**: Code shows what, comments explain why
5. **Keep in sync**: Update docstrings when code changes

## Verification

1. Run `python -m py_compile` on modified files
2. Check docstring matches implementation
3. Ensure no stale information
4. Verify imports are correct

## Common Failure Patterns

1. **Describing intent instead of behavior**: Writing "should transcribe audio" instead of "transcribes audio using Whisper model"
2. **Stale docstrings**: Not updating when code behavior changes
3. **Missing edge cases**: Not documenting known failure modes or exceptions
4. **Obvious comments**: Adding "this is a function" style comments
5. **Inconsistent style**: Mixing Google-style, NumPy-style, or no style in the same module
