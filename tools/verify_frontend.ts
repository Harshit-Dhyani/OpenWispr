/**
 * TypeScript verification script for frontend bug fixes.
 *
 * Run with: npx ts-node tools/verify_frontend.ts
 * Or: node --loader ts-node/esm tools/verify_frontend.ts
 */

import * as fs from 'fs';
import * as path from 'path';

// Types
interface VerificationIssue {
  filePath: string;
  lineNumber: number;
  checkName: string;
  message: string;
  severity: 'error' | 'warning' | 'info';
}

interface CheckResult {
  checkName: string;
  passed: boolean;
  issues: VerificationIssue[];
}

// Utility functions
function findFiles(dir: string, extensions: string[]): string[] {
  const files: string[] = [];

  if (!fs.existsSync(dir)) {
    return files;
  }

  const items = fs.readdirSync(dir);
  for (const item of items) {
    const fullPath = path.join(dir, item);
    const stat = fs.statSync(fullPath);

    if (stat.isDirectory()) {
      files.push(...findFiles(fullPath, extensions));
    } else if (extensions.some((ext) => item.endsWith(ext))) {
      files.push(fullPath);
    }
  }

  return files;
}

function getLineNumber(content: string, index: number): number {
  return content.substring(0, index).split('\n').length;
}

// Check functions
function checkEventSourceCleanup(filePath: string, content: string): VerificationIssue[] {
  const issues: VerificationIssue[] = [];

  // Check if file uses EventSource directly
  if (!content.includes('EventSource')) {
    return issues;
  }

  // Skip files that use useEventSource hook (it handles cleanup internally)
  if (content.includes('useEventSource')) {
    return issues;
  }

  // Check for EventSource instantiation
  const esRegex = /new\s+EventSource\s*\(/g;
  let match;
  while ((match = esRegex.exec(content)) !== null) {
    const lineNum = getLineNumber(content, match.index);

    // Check for cleanup (close() call)
    if (!content.includes('.close()')) {
      issues.push({
        filePath,
        lineNumber: lineNum,
        checkName: 'eventsource_cleanup',
        message: 'EventSource instantiated but no .close() call found',
        severity: 'error',
      });
    }
  }

  return issues;
}

function checkUseEffectCleanup(filePath: string, content: string): VerificationIssue[] {
  const issues: VerificationIssue[] = [];

  // Check if file uses useEffect
  if (!content.includes('useEffect')) {
    return issues;
  }

  // Check for potential memory leaks in useEffect
  const useEffectRegex = /useEffect\s*\(\s*\(\s*\)\s*=>\s*\{/g;
  let match;

  while ((match = useEffectRegex.exec(content)) !== null) {
    const startIndex = match.index;
    const lineNum = getLineNumber(content, startIndex);

    // Look for the effect body - simplified check
    const afterEffect = content.substring(startIndex);

    // Check for subscriptions that need cleanup
    const needsCleanupPatterns = [
      { pattern: 'addEventListener', name: 'event listener' },
      { pattern: 'setInterval', name: 'interval' },
      { pattern: 'setTimeout', name: 'timeout' },
      { pattern: 'EventSource', name: 'EventSource' },
      { pattern: 'WebSocket', name: 'WebSocket' },
    ];

    for (const { pattern, name } of needsCleanupPatterns) {
      if (afterEffect.includes(pattern)) {
        // Check if there's a cleanup function
        if (!afterEffect.includes('return () =>') && !afterEffect.includes('return function')) {
          issues.push({
            filePath,
            lineNumber: lineNum,
            checkName: 'useeffect_cleanup',
            message: `useEffect uses ${name} but may lack cleanup function`,
            severity: 'warning',
          });
        }
      }
    }
  }

  return issues;
}

function checkTimerCleanup(filePath: string, content: string): VerificationIssue[] {
  const issues: VerificationIssue[] = [];

  // Check for setInterval without clearInterval
  const setIntervalRegex = /setInterval\s*\(/g;
  let match;
  while ((match = setIntervalRegex.exec(content)) !== null) {
    const lineNum = getLineNumber(content, match.index);

    if (!content.includes('clearInterval')) {
      issues.push({
        filePath,
        lineNumber: lineNum,
        checkName: 'interval_cleanup',
        message: 'setInterval used without clearInterval in cleanup',
        severity: 'error',
      });
    }
  }

  // Check for setTimeout that should be cleared
  const setTimeoutRegex = /setTimeout\s*\(/g;
  while ((match = setTimeoutRegex.exec(content)) !== null) {
    const lineNum = getLineNumber(content, match.index);

    if (!content.includes('clearTimeout')) {
      issues.push({
        filePath,
        lineNumber: lineNum,
        checkName: 'timeout_cleanup',
        message: 'setTimeout used without clearTimeout in cleanup',
        severity: 'error',
      });
    }
  }

  return issues;
}

function checkTypeSafety(filePath: string, content: string): VerificationIssue[] {
  const issues: VerificationIssue[] = [];

  // Check for 'any' types
  const anyTypeRegex = /:\s*any\b/g;
  let match;
  while ((match = anyTypeRegex.exec(content)) !== null) {
    const lineNum = getLineNumber(content, match.index);

    issues.push({
      filePath,
      lineNumber: lineNum,
      checkName: 'type_safety',
      message: "Use of 'any' type - prefer specific types or 'unknown'",
      severity: 'warning',
    });
  }

  // Check for implicit any in function parameters
  const implicitAnyRegex = /function\s+\w+\s*\(\s*\w+\s*\)/g;
  while ((match = implicitAnyRegex.exec(content)) !== null) {
    const lineNum = getLineNumber(content, match.index);

    issues.push({
      filePath,
      lineNumber: lineNum,
      checkName: 'implicit_any',
      message: 'Function parameter lacks type annotation',
      severity: 'warning',
    });
  }

  return issues;
}

function checkErrorHandling(filePath: string, content: string): VerificationIssue[] {
  const issues: VerificationIssue[] = [];

  // Check for empty catch blocks
  const emptyCatchRegex = /catch\s*\([^)]*\)\s*\{\s*\}/g;
  let match;
  while ((match = emptyCatchRegex.exec(content)) !== null) {
    const lineNum = getLineNumber(content, match.index);

    issues.push({
      filePath,
      lineNumber: lineNum,
      checkName: 'empty_catch',
      message: 'Empty catch block - should handle or log error',
      severity: 'error',
    });
  }

  // Check for catch with just console.log
  const consoleCatchRegex = /catch\s*\([^)]*\)\s*\{\s*console\.log/g;
  while ((match = consoleCatchRegex.exec(content)) !== null) {
    const lineNum = getLineNumber(content, match.index);

    issues.push({
      filePath,
      lineNumber: lineNum,
      checkName: 'weak_error_handling',
      message: 'Catch block only logs error - consider proper error handling',
      severity: 'warning',
    });
  }

  return issues;
}

function checkMissingDependencies(filePath: string, content: string): VerificationIssue[] {
  const issues: VerificationIssue[] = [];

  // Check for useCallback with empty dependency array that uses external values
  const useCallbackRegex = /useCallback\s*\([^,]+,\s*\[\s*\]\s*\)/g;
  let match;
  while ((match = useCallbackRegex.exec(content)) !== null) {
    const lineNum = getLineNumber(content, match.index);

    issues.push({
      filePath,
      lineNumber: lineNum,
      checkName: 'usecallback_deps',
      message: 'useCallback with empty dependency array - verify this is intentional',
      severity: 'warning',
    });
  }

  // Check for useEffect with potentially missing dependencies
  const useEffectRegex = /useEffect\s*\([^)]+,\s*\[\s*\]\s*\)/g;
  while ((match = useEffectRegex.exec(content)) !== null) {
    const lineNum = getLineNumber(content, match.index);

    issues.push({
      filePath,
      lineNumber: lineNum,
      checkName: 'useeffect_deps',
      message: 'useEffect with empty dependency array - verify this is intentional',
      severity: 'info',
    });
  }

  return issues;
}

function checkReactHookRules(filePath: string, content: string): VerificationIssue[] {
  const issues: VerificationIssue[] = [];

  // Check for hooks inside loops or conditions (simplified check)
  const lines = content.split('\n');
  let inConditional = false;
  let conditionalDepth = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Track conditional depth
    if (/\bif\s*\(/g.test(line) || /\bwhile\s*\(/g.test(line) || /\bfor\s*\(/g.test(line)) {
      inConditional = true;
      conditionalDepth++;
    }
    if (line.includes('{')) {
      // Simple brace counting
    }
    if (line.includes('}')) {
      conditionalDepth = Math.max(0, conditionalDepth - 1);
      if (conditionalDepth === 0) {
        inConditional = false;
      }
    }

    // Check for hook calls inside conditionals
    if (inConditional && conditionalDepth > 0) {
      const hookRegex = /\b(useState|useEffect|useCallback|useMemo|useRef|useContext)\s*\(/g;
      if (hookRegex.test(line)) {
        issues.push({
          filePath,
          lineNumber: i + 1,
          checkName: 'hook_rules',
          message: 'React Hook called inside conditional - violates Rules of Hooks',
          severity: 'error',
        });
      }
    }
  }

  return issues;
}

function checkStateMutation(filePath: string, content: string): VerificationIssue[] {
  const issues: VerificationIssue[] = [];

  // Check for direct state mutation
  const mutationPatterns = [
    /setState\s*\(\s*state\s*\./g, // setState(state.something)
    /state\.[\w]+\s*=/g, // state.something =
    /state\.[\w]+\s*\.push/g, // state.something.push
  ];

  for (const pattern of mutationPatterns) {
    let match;
    while ((match = pattern.exec(content)) !== null) {
      const lineNum = getLineNumber(content, match.index);

      issues.push({
        filePath,
        lineNumber: lineNum,
        checkName: 'state_mutation',
        message: 'Potential direct state mutation - use setter or spread operator',
        severity: 'error',
      });
    }
  }

  return issues;
}

// Main verification class
class FrontendVerifier {
  private projectRoot: string;
  private issues: VerificationIssue[] = [];
  private checkResults: CheckResult[] = [];

  constructor(projectRoot: string = process.cwd()) {
    this.projectRoot = projectRoot;
  }

  scanFiles(): string[] {
    const srcDir = path.join(this.projectRoot, 'app', 'desktop', 'frontend', 'src');
    return findFiles(srcDir, ['.ts', '.tsx']);
  }

  runChecks(files: string[]): CheckResult[] {
    const checks = [
      { name: 'EventSource cleanup', fn: checkEventSourceCleanup },
      { name: 'useEffect cleanup', fn: checkUseEffectCleanup },
      { name: 'Timer cleanup', fn: checkTimerCleanup },
      { name: 'Type safety', fn: checkTypeSafety },
      { name: 'Error handling', fn: checkErrorHandling },
      { name: 'Hook dependencies', fn: checkMissingDependencies },
      { name: 'Rules of Hooks', fn: checkReactHookRules },
      { name: 'State mutation', fn: checkStateMutation },
    ];

    for (const check of checks) {
      console.log(`  Running ${check.name}...`);
      const checkIssues: VerificationIssue[] = [];

      for (const file of files) {
        try {
          const content = fs.readFileSync(file, 'utf-8');
          const issues = check.fn(file, content);
          checkIssues.push(...issues);
        } catch (error) {
          checkIssues.push({
            filePath: file,
            lineNumber: 1,
            checkName: 'file_read',
            message: `Failed to read file: ${error}`,
            severity: 'error',
          });
        }
      }

      this.issues.push(...checkIssues);
      const errors = checkIssues.filter((i) => i.severity === 'error');
      this.checkResults.push({
        checkName: check.name,
        passed: errors.length === 0,
        issues: checkIssues,
      });
    }

    return this.checkResults;
  }

  verifyCriticalFixes(): CheckResult {
    const issues: VerificationIssue[] = [];

    // Check useEventSource.ts specifically
    const useEventSourcePath = path.join(
      this.projectRoot,
      'app',
      'desktop',
      'frontend',
      'src',
      'hooks',
      'useEventSource.ts'
    );

    if (fs.existsSync(useEventSourcePath)) {
      const content = fs.readFileSync(useEventSourcePath, 'utf-8');

      // Check for EventSource close
      if (!content.includes('.close()')) {
        issues.push({
          filePath: useEventSourcePath,
          lineNumber: 1,
          checkName: 'eventsource_cleanup',
          message: 'useEventSource hook missing EventSource.close() cleanup',
          severity: 'error',
        });
      }

      // Check for clearTimeout
      if (!content.includes('clearTimeout')) {
        issues.push({
          filePath: useEventSourcePath,
          lineNumber: 1,
          checkName: 'timeout_cleanup',
          message: 'useEventSource hook missing clearTimeout cleanup',
          severity: 'error',
        });
      }

      // Check for clearInterval
      if (!content.includes('clearInterval')) {
        issues.push({
          filePath: useEventSourcePath,
          lineNumber: 1,
          checkName: 'interval_cleanup',
          message: 'useEventSource hook missing clearInterval cleanup',
          severity: 'error',
        });
      }

      // Check for max reconnect limit
      if (!content.includes('maxReconnectAttempts')) {
        issues.push({
          filePath: useEventSourcePath,
          lineNumber: 1,
          checkName: 'reconnect_limit',
          message: 'useEventSource should have max reconnect attempts limit',
          severity: 'warning',
        });
      }
    }

    this.issues.push(...issues);
    const errors = issues.filter((i) => i.severity === 'error');
    const result: CheckResult = {
      checkName: 'critical_fixes',
      passed: errors.length === 0,
      issues,
    };
    this.checkResults.push(result);

    return result;
  }

  printReport(): boolean {
    console.log('\n' + '='.repeat(60));
    console.log('SUMMARY');
    console.log('='.repeat(60));

    const allErrors = this.issues.filter((i) => i.severity === 'error');
    const allWarnings = this.issues.filter((i) => i.severity === 'warning');

    for (const result of this.checkResults) {
      const status = result.passed ? 'PASS' : 'FAIL';
      console.log(`  [${status}] ${result.checkName}`);
    }

    console.log(`\nTotal: ${allErrors.length} errors, ${allWarnings.length} warnings`);

    if (allErrors.length > 0) {
      console.log('\nERRORS:');
      for (const issue of allErrors.slice(0, 10)) {
        console.log(`  ${issue.filePath}:${issue.lineNumber} [${issue.checkName}] ${issue.message}`);
      }
      if (allErrors.length > 10) {
        console.log(`  ... and ${allErrors.length - 10} more errors`);
      }
    }

    return allErrors.length === 0;
  }

  run(): boolean {
    console.log('='.repeat(60));
    console.log('TRANSCRIPTA FRONTEND VERIFICATION');
    console.log('='.repeat(60));
    console.log();

    const files = this.scanFiles();
    console.log(`Scanned ${files.length} TypeScript files`);
    console.log();

    console.log('Running checks...');
    this.runChecks(files);
    console.log();

    console.log('Checking critical fixes...');
    this.verifyCriticalFixes();

    return this.printReport();
  }
}

// Run if called directly
if (require.main === module) {
  const verifier = new FrontendVerifier();
  const success = verifier.run();
  process.exit(success ? 0 : 1);
}

export { FrontendVerifier, VerificationIssue, CheckResult };
