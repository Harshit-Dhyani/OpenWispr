#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const WORKSPACE_ROOT = path.resolve(__dirname, '..');
const SUPPORTED_SUBSYSTEMS = ['api', 'audio', 'config', 'core', 'electron', 'stem', 'storage', 'stt', 'ui'];
const INCLUDED_EXTENSIONS = new Set(['.py', '.js', '.cjs', '.mjs', '.ts', '.tsx', '.jsx', '.json', '.css', '.html']);
const EXCLUDED_DIRECTORIES = new Set([
  '__pycache__',
  '.pytest_cache',
  '.mypy_cache',
  '.ruff_cache',
  'node_modules',
  'dist',
  'build',
  'release',
  'coverage',
  'test-results',
  'out',
  'win-unpacked',
  'mac-unpacked',
  'linux-unpacked',
]);
const EXCLUDED_FILE_EXTENSIONS = new Set([
  '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.bmp', '.webp', '.avif', '.mp4', '.avi', '.mov', '.mp3', '.wav', '.ogg', '.flac', '.zip', '.gz', '.7z', '.rar', '.bin', '.exe', '.dll', '.so', '.dylib', '.map', '.pyc', '.pyo', '.ttf', '.otf', '.woff', '.woff2', '.pdf'
]);
const DEFAULT_TARGET_CHARS = 90000;
const DEFAULT_HARD_MAX_CHARS = 120000;

function parsePositiveInt(value, flagName) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`${flagName} must be a positive integer.`);
  }
  return parsed;
}

function parseArgs(argv) {
  const options = {
    clean: false,
    dryRun: false,
    targetChars: DEFAULT_TARGET_CHARS,
    hardMaxChars: DEFAULT_HARD_MAX_CHARS,
    scope: null,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--clean') {
      options.clean = true;
      continue;
    }
    if (arg === '--dry-run') {
      options.dryRun = true;
      continue;
    }
    if (arg === '--scope') {
      const value = argv[index + 1];
      if (!value) {
        throw new Error('--scope requires a comma-separated value.');
      }
      options.scope = value.split(',').map((item) => item.trim()).filter(Boolean);
      index += 1;
      continue;
    }
    if (arg.startsWith('--scope=')) {
      options.scope = arg.slice('--scope='.length).split(',').map((item) => item.trim()).filter(Boolean);
      continue;
    }
    if (arg === '--max-chars') {
      const value = argv[index + 1];
      if (!value) {
        throw new Error('--max-chars requires a numeric value.');
      }
      options.targetChars = parsePositiveInt(value, '--max-chars');
      index += 1;
      continue;
    }
    if (arg.startsWith('--max-chars=')) {
      options.targetChars = parsePositiveInt(arg.slice('--max-chars='.length), '--max-chars');
      continue;
    }
    if (arg === '--hard-max-chars') {
      const value = argv[index + 1];
      if (!value) {
        throw new Error('--hard-max-chars requires a numeric value.');
      }
      options.hardMaxChars = parsePositiveInt(value, '--hard-max-chars');
      index += 1;
      continue;
    }
    if (arg.startsWith('--hard-max-chars=')) {
      options.hardMaxChars = parsePositiveInt(arg.slice('--hard-max-chars='.length), '--hard-max-chars');
      continue;
    }
    if (arg === '--help' || arg === '-h') {
      options.help = true;
      continue;
    }
    throw new Error(`Unknown argument: ${arg}`);
  }

  if (options.hardMaxChars < options.targetChars) {
    throw new Error('--hard-max-chars must be greater than or equal to --max-chars.');
  }

  return options;
}

function createContext(rootDir = WORKSPACE_ROOT) {
  const repoRoot = path.resolve(rootDir);
  return {
    repoRoot,
    appRoot: path.join(repoRoot, 'app'),
    codeRoot: path.join(repoRoot, 'code'),
  };
}

function toPosixPath(value) {
  return value.split(path.sep).join('/');
}

function resolveSubsystems(context, requestedScope) {
  const available = SUPPORTED_SUBSYSTEMS.filter((name) => fs.existsSync(path.join(context.appRoot, name)) && fs.statSync(path.join(context.appRoot, name)).isDirectory());
  if (!requestedScope || requestedScope.length === 0) {
    return available;
  }

  const invalid = requestedScope.filter((name) => !SUPPORTED_SUBSYSTEMS.includes(name));
  if (invalid.length > 0) {
    throw new Error(`Unsupported subsystem scope: ${invalid.join(', ')}`);
  }

  return requestedScope.filter((name) => available.includes(name));
}

function shouldSkipDirectory(relativePath) {
  const parts = relativePath.split(/[\\/]+/).filter(Boolean);
  return parts.some((part) => EXCLUDED_DIRECTORIES.has(part));
}

function shouldIncludeFile(absolutePath, relativePath) {
  if (shouldSkipDirectory(relativePath)) {
    return false;
  }
  const extension = path.extname(absolutePath).toLowerCase();
  if (!INCLUDED_EXTENSIONS.has(extension)) {
    return false;
  }
  if (EXCLUDED_FILE_EXTENSIONS.has(extension)) {
    return false;
  }
  return true;
}

function walkDirectory(context, startDir, onFile) {
  const entries = fs.readdirSync(startDir, { withFileTypes: true }).sort((left, right) => left.name.localeCompare(right.name));
  for (const entry of entries) {
    const absolutePath = path.join(startDir, entry.name);
    const relativePath = path.relative(context.repoRoot, absolutePath);
    if (entry.isDirectory()) {
      if (shouldSkipDirectory(relativePath)) {
        continue;
      }
      walkDirectory(context, absolutePath, onFile);
      continue;
    }
    onFile(absolutePath, relativePath);
  }
}

function collectSubsystemFiles(context, subsystem) {
  const rootDir = path.join(context.appRoot, subsystem);
  const includedFiles = [];
  let excludedFileCount = 0;

  walkDirectory(context, rootDir, (absolutePath, relativePath) => {
    const normalizedRelativePath = toPosixPath(relativePath);
    if (!shouldIncludeFile(absolutePath, normalizedRelativePath)) {
      excludedFileCount += 1;
      return;
    }
    includedFiles.push({
      absolutePath,
      relativePath: normalizedRelativePath,
      contents: fs.readFileSync(absolutePath, 'utf8'),
    });
  });

  includedFiles.sort((left, right) => left.relativePath.localeCompare(right.relativePath));

  return {
    subsystem,
    sourceRoot: toPosixPath(path.relative(context.repoRoot, rootDir)),
    includedFiles,
    excludedFileCount,
  };
}

function formatFileBlock(relativePath, contents) {
  return `===== BEGIN FILE: ${relativePath} =====\n${contents}\n===== END FILE: ${relativePath} =====\n`;
}

function formatFileFragment(relativePath, startLine, endLine, contents) {
  const label = `${relativePath} (lines ${startLine}-${endLine})`;
  return `===== BEGIN FILE: ${label} =====\n${contents}\n===== END FILE: ${label} =====\n`;
}

function createFormattedEntriesForFile(relativePath, contents, hardMaxChars) {
  const wholeBlock = formatFileBlock(relativePath, contents);
  if (wholeBlock.length <= hardMaxChars) {
    return [{
      displayPath: relativePath,
      output: wholeBlock,
      charCount: wholeBlock.length,
    }];
  }

  const lines = contents.split(/\r?\n/);
  const entries = [];
  let startIndex = 0;

  while (startIndex < lines.length) {
    let endIndex = startIndex;
    let fragment = '';
    while (endIndex < lines.length) {
      const candidate = fragment.length === 0 ? lines[endIndex] : `${fragment}\n${lines[endIndex]}`;
      const candidateOutput = formatFileFragment(relativePath, startIndex + 1, endIndex + 1, candidate);
      if (candidateOutput.length > hardMaxChars && endIndex > startIndex) {
        break;
      }
      fragment = candidate;
      endIndex += 1;
      if (formatFileFragment(relativePath, startIndex + 1, endIndex, fragment).length > hardMaxChars) {
        fragment = lines[startIndex];
        endIndex = startIndex + 1;
        break;
      }
    }

    const chunkEndLine = Math.max(startIndex + 1, endIndex);
    const output = formatFileFragment(relativePath, startIndex + 1, chunkEndLine, fragment);
    entries.push({
      displayPath: `${relativePath} (lines ${startIndex + 1}-${chunkEndLine})`,
      output,
      charCount: output.length,
    });
    startIndex = endIndex;
  }

  return entries;
}

function createEmptyChunk(subsystem) {
  return {
    subsystem,
    entries: [],
    charCount: 0,
  };
}

function finalizeChunk(chunk, sourceRoot, chunkIndex) {
  const fileList = chunk.entries.map((entry) => `- ${entry.displayPath}`).join('\n');
  const header = [
    `Subsystem: ${chunk.subsystem}`,
    `Source root: ${sourceRoot}`,
    `Chunk: ${chunkIndex}`,
    'Files:',
    fileList || '- (empty)',
    '',
  ].join('\n');
  const body = chunk.entries.map((entry) => entry.output).join('\n');
  return `${header}${body}`;
}

function splitEntriesIntoChunks(subsystem, sourceRoot, fileEntries, targetChars, hardMaxChars) {
  const chunks = [];
  let current = createEmptyChunk(subsystem);

  for (const fileEntry of fileEntries) {
    const formattedEntries = createFormattedEntriesForFile(fileEntry.relativePath, fileEntry.contents, hardMaxChars);
    for (const entry of formattedEntries) {
      if (current.entries.length > 0 && current.charCount + entry.charCount > targetChars) {
        chunks.push(current);
        current = createEmptyChunk(subsystem);
      }
      current.entries.push(entry);
      current.charCount += entry.charCount;
    }
  }

  if (current.entries.length > 0 || chunks.length === 0) {
    chunks.push(current);
  }

  return chunks.map((chunk, index) => {
    const filename = `${subsystem}-part-${String(index + 1).padStart(3, '0')}.txt`;
    return {
      filename,
      contents: finalizeChunk(chunk, sourceRoot, index + 1),
      fileList: chunk.entries.map((entry) => entry.displayPath),
    };
  });
}

function buildExportResult(options = {}, rootDir = WORKSPACE_ROOT) {
  const mergedOptions = {
    clean: Boolean(options.clean),
    dryRun: Boolean(options.dryRun),
    targetChars: options.targetChars || DEFAULT_TARGET_CHARS,
    hardMaxChars: options.hardMaxChars || DEFAULT_HARD_MAX_CHARS,
    scope: options.scope || null,
  };
  const context = createContext(rootDir);
  const subsystems = resolveSubsystems(context, mergedOptions.scope);
  const generatedAt = new Date().toISOString();
  const exportSettings = {
    targetChars: mergedOptions.targetChars,
    hardMaxChars: mergedOptions.hardMaxChars,
    scope: subsystems,
    sourceOnly: true,
  };

  const subsystemResults = [];
  const manifestSubsystems = {};

  for (const subsystem of subsystems) {
    const collected = collectSubsystemFiles(context, subsystem);
    const chunks = splitEntriesIntoChunks(subsystem, collected.sourceRoot, collected.includedFiles, mergedOptions.targetChars, mergedOptions.hardMaxChars);
    const totalCharacterCount = chunks.reduce((total, chunk) => total + chunk.contents.length, 0);
    subsystemResults.push({
      subsystem,
      sourceRoot: collected.sourceRoot,
      includedFileCount: collected.includedFiles.length,
      excludedFileCount: collected.excludedFileCount,
      chunkCount: chunks.length,
      chunkFiles: chunks,
      totalCharacterCount,
    });
    manifestSubsystems[subsystem] = {
      sourceRoot: collected.sourceRoot,
      includedFileCount: collected.includedFiles.length,
      excludedFileCount: collected.excludedFileCount,
      chunkCount: chunks.length,
      chunkFiles: chunks.map((chunk) => chunk.filename),
      totalCharacterCount,
      generatedAt,
      exportSettings,
    };
  }

  return {
    context,
    generatedAt,
    exportSettings,
    subsystems: subsystemResults,
    manifest: {
      generatedAt,
      exportSettings,
      subsystems: manifestSubsystems,
    },
  };
}

function writeExportOutputs(exportResult, options) {
  const { context } = exportResult;
  if (options.clean && fs.existsSync(context.codeRoot)) {
    fs.rmSync(context.codeRoot, { recursive: true, force: true });
  }
  fs.mkdirSync(context.codeRoot, { recursive: true });

  for (const subsystem of exportResult.subsystems) {
    const subsystemDir = path.join(context.codeRoot, subsystem.subsystem);
    fs.mkdirSync(subsystemDir, { recursive: true });
    for (const chunk of subsystem.chunkFiles) {
      fs.writeFileSync(path.join(subsystemDir, chunk.filename), chunk.contents, 'utf8');
    }
  }

  fs.writeFileSync(path.join(context.codeRoot, 'index.json'), `${JSON.stringify(exportResult.manifest, null, 2)}\n`, 'utf8');
}

function printSummary(exportResult, options) {
  for (const subsystem of exportResult.subsystems) {
    const suffix = options.dryRun ? ' (dry-run)' : '';
    console.log(`${subsystem.subsystem}: ${subsystem.includedFileCount} files, ${subsystem.chunkCount} chunks, ${subsystem.totalCharacterCount} chars${suffix}`);
  }
  console.log(`Manifest: ${toPosixPath(path.relative(exportResult.context.repoRoot, path.join(exportResult.context.codeRoot, 'index.json')))}`);
}

function printHelp() {
  console.log([
    'Usage: node scripts/export-code-for-chatgpt.cjs [options]',
    '',
    'Options:',
    '  --scope api,core,stt    Export only specific subsystems',
    '  --clean                 Remove previous code/ output before writing',
    '  --max-chars 90000       Target characters per chunk',
    '  --hard-max-chars 120000 Hard cap before splitting a single file by lines',
    '  --dry-run               Print export plan without writing files',
  ].join('\n'));
}

function main(argv = process.argv.slice(2), rootDir = WORKSPACE_ROOT) {
  const options = parseArgs(argv);
  if (options.help) {
    printHelp();
    return null;
  }

  const exportResult = buildExportResult(options, rootDir);
  if (!options.dryRun) {
    writeExportOutputs(exportResult, options);
  }
  printSummary(exportResult, options);
  return exportResult;
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}

module.exports = {
  DEFAULT_HARD_MAX_CHARS,
  DEFAULT_TARGET_CHARS,
  SUPPORTED_SUBSYSTEMS,
  buildExportResult,
  collectSubsystemFiles,
  createContext,
  createFormattedEntriesForFile,
  main,
  parseArgs,
  resolveSubsystems,
  splitEntriesIntoChunks,
  shouldIncludeFile,
  shouldSkipDirectory,
  toPosixPath,
  writeExportOutputs,
};
