const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const repoRoot = path.resolve(__dirname, '../..');
const outputDir = path.join(repoRoot, 'reports');
const outputPath = path.join(outputDir, 'tree.txt');

function runGit(args) {
  return execFileSync('git', args, {
    cwd: repoRoot,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  }).trim();
}

function insertPath(root, relativePath) {
  const parts = relativePath.split('/').filter(Boolean);
  let node = root;

  for (const part of parts) {
    if (!node.children.has(part)) {
      node.children.set(part, { name: part, children: new Map(), isFile: false });
    }
    node = node.children.get(part);
  }

  node.isFile = true;
}

function formatTree(node, prefix = '') {
  const entries = [...node.children.values()].sort((a, b) => {
    if (a.isFile !== b.isFile) {
      return a.isFile ? 1 : -1;
    }
    return a.name.localeCompare(b.name);
  });

  return entries.flatMap((entry, index) => {
    const isLast = index === entries.length - 1;
    const branch = `${prefix}${isLast ? '└── ' : '├── '}${entry.name}`;
    if (entry.isFile || entry.children.size === 0) {
      return [branch];
    }

    const childPrefix = `${prefix}${isLast ? '    ' : '│   '}`;
    return [branch, ...formatTree(entry, childPrefix)];
  });
}

const fileList = runGit(['ls-files', '--cached', '--others', '--exclude-standard'])
  .split(/\r?\n/)
  .map((line) => line.trim())
  .filter(Boolean);

const root = { name: '.', children: new Map(), isFile: false };
for (const file of fileList) {
  insertPath(root, file.replace(/\\/g, '/'));
}

const lines = [
  '# OpenWispr Tree',
  '',
  `Generated: ${new Date().toISOString()}`,
  `Files: ${fileList.length}`,
  '',
  '.',
  ...formatTree(root),
  '',
];

fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(outputPath, lines.join('\n'), 'utf8');

console.log(`Wrote ${path.relative(repoRoot, outputPath)}`);
