const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const repoRoot = path.resolve(__dirname, '..');
const outputDir = path.join(repoRoot, 'reports');
const outputPath = path.join(outputDir, 'changes-since-last-commit.md');

function runGit(args, allowFailure = false) {
  try {
    return execFileSync('git', args, {
      cwd: repoRoot,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    }).trim();
  } catch (error) {
    if (allowFailure) {
      return '';
    }
    throw error;
  }
}

const head = runGit(['rev-parse', '--short', 'HEAD']);
const statusShort = runGit(['status', '--short']);
const nameStatus = runGit(['diff', '--name-status', 'HEAD']);
const diffStat = runGit(['diff', '--stat', 'HEAD']);
const untracked = runGit(['ls-files', '--others', '--exclude-standard'], true);

const lines = [
  '# Changes Since Last Commit',
  '',
  `Generated: ${new Date().toISOString()}`,
  `Base commit: ${head}`,
  '',
  '## Git Status',
  '',
  '```text',
  statusShort || 'Working tree clean',
  '```',
  '',
  '## Changed Files vs HEAD',
  '',
  '```text',
  nameStatus || 'No tracked file changes',
  '```',
  '',
  '## Diff Stat vs HEAD',
  '',
  '```text',
  diffStat || 'No tracked file changes',
  '```',
  '',
  '## Untracked Files',
  '',
  '```text',
  untracked || 'No untracked files',
  '```',
  '',
];

fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(outputPath, lines.join('\n'), 'utf8');

console.log(`Wrote ${path.relative(repoRoot, outputPath)}`);
