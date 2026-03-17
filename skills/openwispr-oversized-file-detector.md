# OpenWispr Oversized File Detector

## Purpose
Detect files that exceed recommended size limits and need to be split.

## When to Use
- Before making large changes to existing files
- When adding new features that increase file size
- During code review
- When investigating slow builds or imports

## When NOT to Use
- For small utility files
- For generated files
- For configuration files
- For already-split module directories

## Discovery Steps
1. Check file sizes: `Get-ChildItem -Path app -Recurse -Filter "*.py" | ForEach-Object { [PSCustomObject]@{Path=$_.FullName;Lines=(Get-Content $_.FullName).Count} } | Sort-Object Lines -Descending | Select-Object -First 20`
2. Check JavaScript/TypeScript: `Get-ChildItem -Path app/electron/frontend/src -Recurse -Include "*.ts","*.tsx" | ForEach-Object { [PSCustomObject]@{Path=$_.FullName;Lines=(Get-Content $_.FullName).Count} } | Sort-Object Lines -Descending`
3. Check for files approaching limits:
   - Python: 500 lines
   - Electron index.js: 1000 lines
   - App.tsx: 1500 lines
   - Frontend components: 500 lines
4. Check if file has mixed responsibilities

## Verification Requirements
- Python modules should stay under 500 lines
- Electron main entry (index.js) must stay under 1000 lines
- Frontend App.tsx should stay under 1500 lines
- Frontend components (MainContent, FloatingWindow) should stay under 500 lines
- Split by responsibility, not arbitrary chunks

## Common Failure Patterns
- Adding code to existing large files instead of splitting
- Mixing multiple responsibilities in one file
- Not extracting route handlers to separate files
- Not splitting UI components by feature

## Safe Edit Rules
- Split by responsibility, not arbitrary line count
- When splitting, update all imports
- Ensure new files have single responsibility
- Verify imports resolve after split
- Run tests after splitting files
