# OpenWispr Model Routing Test

## Purpose
Verify that model selection correctly routes to the appropriate model based on audio source (microphone vs system audio).

## When to Use
- When modifying model selection logic
- When adding new models
- When changing model routing rules
- When debugging why wrong model is used

## When NOT to Use
- For UI changes unrelated to model selection
- For settings changes that don't affect models
- For audio pipeline changes that don't affect routing

## Discovery Steps
1. Check model catalog: `app/core/model_catalog.py`
2. Find model routing logic: `grep -r "model.*routing" --include="*.py"`
3. Check microphone model settings vs system model settings
4. Verify fallback logic when source-specific model is unset
5. Check logs for model selection during dictation vs sessions

## Verification Requirements
- Microphone dictation uses microphone model setting
- System audio sessions use system model setting
- Fallback only occurs when source-specific value is unset
- Model catalog is single source of truth for model metadata
- Routing decisions are logged

## Common Failure Patterns
- Using same model for both microphone and system audio
- Missing fallback logic when source-specific model is unset
- Hardcoding model names instead of using settings
- Not logging model selection decisions
- Changing model catalog without updating consumers

## Safe Edit Rules
- Keep microphone and system model settings separate
- Never hardcode model IDs - use settings and catalog
- Log model selection with clear reasoning
- Test both microphone and system audio paths
- Verify model routing in logs after changes
