/**
 * Model download manager for Whisper models
 * Handles model catalog fetching, download progress, resumable downloads with
 * chunk validation, retry logic, and storage management. Exports: ModelDownloadManager
 * @module modelDownloadManager
 */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { once } = require("events");
const { Readable } = require("stream");
const state = require("../shared/state");

let UndiciAgent = null;
try {
  ({ Agent: UndiciAgent } = require("undici"));
} catch (_error) {
  UndiciAgent = null;
}

const CONNECT_TIMEOUT_MS = 60_000;
const REQUEST_TIMEOUT_MS = 20 * 60 * 1000;
const OPTIONAL_ARTIFACT_FILENAMES = new Set([
  "vocabulary.txt",
  "vocab.json",
  "vocabulary.json",
  "merges.txt",
]);
const NETWORK_RETRYABLE_CODES = new Set([
  "ECONNRESET",
  "ETIMEDOUT",
  "ENOTFOUND",
  "ECONNREFUSED",
  "EPIPE",
  "UND_ERR_CONNECT_TIMEOUT",
  "UND_ERR_HEADERS_TIMEOUT",
  "UND_ERR_BODY_TIMEOUT",
  "UND_ERR_SOCKET",
]);

// Logger utility for model downloads
const logger = {
  info: (msg, ...args) => console.log(`[models:download] ${msg}`, ...args),
  error: (msg, ...args) => console.error(`[models:download] ${msg}`, ...args),
  warn: (msg, ...args) => console.warn(`[models:download] ${msg}`, ...args),
  debug: (msg, ...args) => {
    if (process.env.DEBUG_MODEL_DOWNLOAD) {
      console.log(`[models:download:debug] ${msg}`, ...args);
    }
  }
};

class ModelDownloadManager {
  constructor({ getApiOrigin, getUserDataPath, emit }) {
    this.getApiOrigin = getApiOrigin;
    this.getUserDataPath = getUserDataPath;
    this.emit = emit;
    this.downloads = new Map();
    this.downloadSequence = 0;
    this.hfToken = process.env.HF_TOKEN || process.env.HUGGINGFACE_HUB_TOKEN || "";
    this.fetchDispatcher = UndiciAgent
      ? new UndiciAgent({
          connect: { timeout: CONNECT_TIMEOUT_MS },
          headersTimeout: REQUEST_TIMEOUT_MS,
          bodyTimeout: REQUEST_TIMEOUT_MS,
        })
      : null;
  }

  getModelsRoot() {
    return path.join(this.getUserDataPath(), "models");
  }

  async getCatalog() {
    const response = await fetch(`${this.getApiOrigin()}/api/models/catalog`);
    if (!response.ok) {
      throw new Error(`Failed to load model catalog (${response.status})`);
    }
    return response.json();
  }

  async downloadModel(modelId, maxRetries = 3) {
    const downloadContext = {
      modelId,
      startTime: new Date().toISOString(),
      userAgent: state.DOWNLOAD_USER_AGENT,
      maxRetries
    };

    logger.info('Starting download:', modelId);
    logger.info('Context:', downloadContext);

    if (this.downloads.has(modelId)) {
      logger.info('Download already in progress for:', modelId);
      return this.downloads.get(modelId).snapshot();
    }

    // Retry loop
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      logger.info(`Attempt ${attempt}/${maxRetries} for model:`, modelId);

      try {
        const result = await this._downloadModelInternal(modelId, downloadContext, attempt);
        logger.info('Download succeeded on attempt', attempt);
        return result;
      } catch (error) {
        this._handleDownloadError(error, attempt, maxRetries, modelId);

        if (!this._isRetryableDownloadError(error) || attempt === maxRetries) {
          logger.error('All retry attempts exhausted for:', modelId);
          throw error;
        }

        const delay = this._computeRetryDelayMs(attempt);
        this.emit("model-download-retrying", {
          model_id: modelId,
          download_id: `${modelId}:retry:${attempt + 1}:${this.downloadSequence + 1}`,
          attempt: attempt + 1,
          status: "retrying",
          bytes_downloaded: 0,
          total_bytes: 0,
          total_bytes_known: false,
          progress: 0,
          speed_bytes_per_sec: 0,
          error: error.message,
        });
        logger.info(`Retrying in ${delay}ms...`);
        await new Promise(r => setTimeout(r, delay));
      }
    }
  }

  _handleDownloadError(error, attempt, maxRetries, modelId) {
    const causeCode = error?.cause?.code;
    const errorContext = {
      attempt,
      maxRetries,
      modelId,
      errorCode: error.code,
      causeCode,
      errorMessage: error.message
    };

    // Log specific error types
    if (error.code === 'ECONNRESET') {
      logger.error('Connection reset by peer - network issue', errorContext);
    } else if (error.code === 'ETIMEDOUT') {
      logger.error('Connection timeout', errorContext);
    } else if (error.code === 'ENOTFOUND') {
      logger.error('DNS lookup failed - check internet connection', errorContext);
    } else if (error.code === 'ECONNREFUSED') {
      logger.error('Connection refused - server may be down', errorContext);
    } else if (error.code === 'EPIPE') {
      logger.error('Broken pipe - connection interrupted', errorContext);
    } else if (causeCode && NETWORK_RETRYABLE_CODES.has(causeCode)) {
      logger.error('Network transport error', errorContext);
    } else {
      logger.error(`Attempt ${attempt} failed:`, error.message);
    }

    if (error.stack) {
      logger.debug('Stack trace:', error.stack);
    }
  }

  async _downloadModelInternal(modelId, downloadContext, attempt) {
    const catalogPayload = await this.getCatalog();
    const entry = (catalogPayload.catalog || []).find((item) => item.id === modelId);
    if (!entry) {
      throw new Error(`Unknown model: ${modelId}`);
    }

    logger.info('Found catalog entry:', {
      modelId: entry.id,
      category: entry.category,
      artifacts: (entry.download_artifacts || []).map(a => a.filename)
    });

    const controller = new AbortController();
    const downloadId = `${modelId}:${Date.now()}:${++this.downloadSequence}`;
    const artifactCount = (entry.download_artifacts || []).length;
    const state = {
      modelId,
      downloadId,
      attempt,
      status: "downloading",
      bytesDownloaded: 0,
      totalBytes: 0,
      totalBytesKnown: false,
      progress: 0,
      speedBytesPerSec: 0,
      error: null,
      currentArtifact: null,
      lastEmittedProgress: 0,
      controller,
      snapshot() {
        return {
          model_id: this.modelId,
          download_id: this.downloadId,
          correlation_id: this.downloadId,
          attempt: this.attempt,
          current_artifact: this.currentArtifact,
          status: this.status,
          bytes_downloaded: this.bytesDownloaded,
          total_bytes: this.totalBytes,
          total_bytes_known: this.totalBytesKnown,
          progress: this.progress,
          speed_bytes_per_sec: this.speedBytesPerSec,
          error: this.error,
        };
      },
    };
    this.downloads.set(modelId, state);
    this.emit("model-download-started", state.snapshot());

    try {
      const installDir = path.join(this.getModelsRoot(), entry.category, entry.id);
      logger.info('Creating install directory:', installDir);
      fs.mkdirSync(installDir, { recursive: true });

      const startedAt = Date.now();
      let completedBytes = 0;
      let totalBytes = 0;
      let knownArtifactCount = 0;
      let lastLogTime = Date.now();

      for (const artifact of entry.download_artifacts || []) {
        state.currentArtifact = artifact.filename;
        const targetPath = path.join(installDir, artifact.filename);
        const tempPath = `${targetPath}.partial`;
        logger.info('Downloading artifact:', {
          filename: artifact.filename,
          url: artifact.url,
          targetPath
        });

        if (fs.existsSync(targetPath)) {
          const existingTargetSize = fs.statSync(targetPath).size;
          if (existingTargetSize >= artifact.min_size_bytes) {
            logger.info('Artifact already present, skipping download:', {
              filename: artifact.filename,
              sizeBytes: existingTargetSize,
            });
            completedBytes += existingTargetSize;
            totalBytes += existingTargetSize;
            knownArtifactCount += 1;
            state.bytesDownloaded = completedBytes;
            state.totalBytes = totalBytes;
            state.totalBytesKnown = knownArtifactCount === artifactCount;
            // Calculate progress based on known artifacts
            let newProgress;
            if (state.totalBytesKnown && totalBytes > 0) {
              newProgress = (completedBytes / totalBytes) * 100;
            } else {
              newProgress = (knownArtifactCount / artifactCount) * 100;
            }
            state.progress = Math.max(state.lastEmittedProgress, newProgress);
            state.lastEmittedProgress = state.progress;
            this.emit("model-download-progress", state.snapshot());
            continue;
          }
        }

        const resumeOffset = fs.existsSync(tempPath) ? fs.statSync(tempPath).size : 0;
        let response = await this.fetchArtifactResponse(entry, artifact, controller.signal, {
          offset: resumeOffset,
        });
        if (response.status === 416 && resumeOffset > 0) {
          const remoteTotal = this._extractContentRangeTotal(response);
          if (remoteTotal > 0 && resumeOffset >= remoteTotal) {
            logger.info('Partial artifact already complete, finalizing existing partial file:', {
              filename: artifact.filename,
              partialBytes: resumeOffset,
              remoteTotal,
            });
            await this._finalizeArtifact(tempPath, targetPath);
            completedBytes += remoteTotal;
            totalBytes += remoteTotal;
            knownArtifactCount += 1;
            state.bytesDownloaded = completedBytes;
            state.totalBytes = totalBytes;
            state.totalBytesKnown = artifactCount > 0 && knownArtifactCount === artifactCount;
            // Calculate progress based on known artifacts
            let newProgress;
            if (state.totalBytesKnown && totalBytes > 0) {
              newProgress = (completedBytes / totalBytes) * 100;
            } else {
              newProgress = (knownArtifactCount / artifactCount) * 100;
            }
            state.progress = Math.max(state.lastEmittedProgress, newProgress);
            state.lastEmittedProgress = state.progress;
            this.emit("model-download-progress", state.snapshot());
            continue;
          }

          logger.warn('Partial artifact is stale, restarting from zero after 416 response:', {
            filename: artifact.filename,
            partialBytes: resumeOffset,
            remoteTotal,
          });
          fs.rmSync(tempPath, { force: true });
          response = await this.fetchArtifactResponse(entry, artifact, controller.signal, { offset: 0 });
        }
        if (response?.status === 404 && this._isOptionalArtifactFilename(artifact.filename)) {
          logger.warn('Optional artifact missing, skipping:', {
            modelId,
            filename: artifact.filename,
            url: response.url || artifact.url,
            statusCode: response.status,
          });
          continue;
        }

        if (!response.ok || !response.body) {
          const headers = this._headersObject(response?.headers);
          const detail = response ? `${response.status} ${response.statusText}` : "no response body";
          throw this._createDownloadError(
            `Download failed for ${artifact.filename} (${detail})`,
            {
              url: response?.url || artifact.url,
              statusCode: response?.status,
              headers,
              partialBytes: resumeOffset,
              retryable: Boolean(response?.status && response.status >= 500),
            },
          );
        }

        const artifactTotal = this._resolveArtifactTotalBytes(response, resumeOffset);
        if (artifactTotal > 0) {
          totalBytes += artifactTotal;
          knownArtifactCount += 1;
        }
        state.totalBytes = totalBytes;
        state.totalBytesKnown = artifactCount > 0 && knownArtifactCount === artifactCount;

        logger.info('Artifact size:', {
          filename: artifact.filename,
          sizeBytes: artifactTotal,
          sizeMB: (artifactTotal / 1024 / 1024).toFixed(2)
        });

        const resumeAccepted = resumeOffset > 0 && response.status === 206;
        const resumedBytes = resumeAccepted ? resumeOffset : 0;
        if (resumeOffset > 0 && !resumeAccepted) {
          logger.warn('Server did not honor Range request, restarting artifact from zero:', {
            filename: artifact.filename,
            requestedOffset: resumeOffset,
            status: response.status,
          });
        }

        let artifactBytesWritten = 0;
        completedBytes += resumedBytes;
        state.bytesDownloaded = completedBytes;
        await this._streamArtifactToDisk({
          response,
          tempPath,
          append: resumeAccepted,
          signal: controller.signal,
          onChunk: (chunkSize) => {
            artifactBytesWritten += chunkSize;
            state.bytesDownloaded = completedBytes + artifactBytesWritten;
            state.totalBytes = totalBytes || state.bytesDownloaded;
            // Calculate progress: use total bytes if known, otherwise use completed bytes
            // scaled by artifact count to estimate progress across all artifacts
            let newProgress;
            if (state.totalBytesKnown && state.totalBytes > 0) {
              newProgress = (state.bytesDownloaded / state.totalBytes) * 100;
            } else if (totalBytes > 0) {
              // Estimate progress assuming equal-sized artifacts
              newProgress = (completedBytes / totalBytes) * 100;
            } else {
              // No total known, estimate based on artifacts completed
              newProgress = (knownArtifactCount / artifactCount) * 100;
            }
            state.progress = Math.max(state.lastEmittedProgress, newProgress);
            state.lastEmittedProgress = state.progress;
            const elapsedSeconds = Math.max((Date.now() - startedAt) / 1000, 0.1);
            state.speedBytesPerSec = state.bytesDownloaded / elapsedSeconds;
            this.emit("model-download-progress", state.snapshot());

            const now = Date.now();
            const progressPct = state.progress;
            if (now - lastLogTime > 5000 || (Math.floor(progressPct) % 10 === 0 && now - lastLogTime > 1000)) {
              logger.info(
                'Progress: %s (%s MB / %s MB at %s MB/s)',
                progressPct.toFixed(1) + '%',
                (state.bytesDownloaded / 1024 / 1024).toFixed(2),
                (Math.max(totalBytes, state.bytesDownloaded) / 1024 / 1024).toFixed(2),
                (state.speedBytesPerSec / 1024 / 1024).toFixed(2),
              );
              lastLogTime = now;
            }
          },
        });
        completedBytes += artifactBytesWritten;
        await this._finalizeArtifact(tempPath, targetPath);

        const fileStat = fs.statSync(targetPath);
        logger.info('Verifying artifact:', {
          filename: artifact.filename,
          size: fileStat.size,
          minRequired: artifact.min_size_bytes
        });

        if (fileStat.size < artifact.min_size_bytes) {
          throw new Error(`Verification failed for ${artifact.filename}: file too small`);
        }
        if (artifact.sha256) {
          logger.info('Computing SHA256 for:', artifact.filename);
          const digest = await this.sha256File(targetPath);
          if (digest !== artifact.sha256) {
            throw new Error(`Verification failed for ${artifact.filename}: sha256 mismatch`);
          }
          logger.info('SHA256 verified for:', artifact.filename);
        }
      }

      state.status = "completed";
      state.totalBytes = Math.max(state.totalBytes, completedBytes);
      state.totalBytesKnown = state.totalBytes > 0;
      state.progress = 100;
      logger.info('Download completed successfully:', {
        modelId,
        totalBytes: state.totalBytes,
        totalMB: (state.totalBytes / 1024 / 1024).toFixed(2),
        duration: ((Date.now() - new Date(downloadContext.startTime).getTime()) / 1000).toFixed(1) + 's'
      });
      this.emit("model-download-completed", state.snapshot());
      return state.snapshot();
    } catch (error) {
      if (controller.signal.aborted) {
        logger.info('Download cancelled for:', modelId);
        state.status = "cancelled";
        state.error = "cancelled";
        this.emit("model-download-cancelled", state.snapshot());
        return state.snapshot();
      }

      logger.error('Download failed:', {
        ...downloadContext,
        attempt,
        error: error.message,
        code: error.code,
        cause: error.cause?.message,
        causeCode: error.cause?.code,
        statusCode: error.statusCode,
        url: error.url,
        headers: error.headers,
        partialBytes: error.partialBytes,
        stack: error.stack
      });

      state.status = "failed";
      state.error = error instanceof Error ? error.message : String(error);
      this.emit("model-download-failed", state.snapshot());
      throw error;
    } finally {
      this.downloads.delete(modelId);
    }
  }

  cancelDownload(modelId) {
    logger.info('Cancelling download for:', modelId);
    const state = this.downloads.get(modelId);
    if (!state) {
      logger.warn('No active download to cancel for:', modelId);
      return { ok: false, error: "not-downloading" };
    }
    state.controller.abort();
    return { ok: true };
  }

  async removeModel(modelId) {
    logger.info('Removing model:', modelId);
    const catalogPayload = await this.getCatalog();
    const entry = (catalogPayload.catalog || []).find((item) => item.id === modelId);
    if (!entry) {
      throw new Error(`Unknown model: ${modelId}`);
    }
    const installDir = path.join(this.getModelsRoot(), entry.category, entry.id);
    if (fs.existsSync(installDir)) {
      logger.info('Removing directory:', installDir);
      fs.rmSync(installDir, { recursive: true, force: true });
    }
    this.emit("model-removed", { model_id: modelId });
    logger.info('Model removed successfully:', modelId);
    return { ok: true, model_id: modelId };
  }

  async sha256File(filePath) {
    return new Promise((resolve, reject) => {
      const hash = crypto.createHash("sha256");
      const stream = fs.createReadStream(filePath);
      stream.on("data", (chunk) => hash.update(chunk));
      stream.on("error", reject);
      stream.on("end", () => resolve(hash.digest("hex")));
    });
  }

  async fetchArtifactResponse(entry, artifact, signal, { offset = 0 } = {}) {
    logger.info('Fetching artifact:', { url: artifact.url, filename: artifact.filename });
    const startedAt = Date.now();

    let response;
    try {
      response = await this._fetchWithTimeout(artifact.url, {
        signal,
        headers: offset > 0 ? { Range: `bytes=${offset}-` } : {},
      });
      logger.info('Primary fetch response:', {
        url: artifact.url,
        resolvedUrl: response.url,
        resolvedHost: this._safeUrlHost(response.url),
        status: response.status,
        ok: response.ok,
        durationMs: Date.now() - startedAt,
      });
    } catch (error) {
      logger.error('Primary fetch failed:', {
        url: artifact.url,
        error: error.message,
        code: error.code
      });
      throw error;
    }

    if (response.ok && response.body) {
      return response;
    }

    const repo = this.extractHuggingFaceRepo(artifact.url);
    if (!repo) {
      logger.warn('Not a HuggingFace URL, no fallback available:', artifact.url);
      return response;
    }

    logger.info('Attempting HuggingFace fallback resolution for repo:', repo);

    const resolvedFilename = await this.resolveHuggingFaceFilename(repo, artifact.filename, signal);
    if (!resolvedFilename || resolvedFilename === artifact.filename) {
      logger.info('No fallback filename resolved, using original response');
      return response;
    }

    const fallbackUrl = `https://huggingface.co/${repo}/resolve/main/${resolvedFilename}?download=true`;
    logger.info('Trying fallback URL:', fallbackUrl);

    try {
      response = await this._fetchWithTimeout(fallbackUrl, {
        signal,
        headers: offset > 0 ? { Range: `bytes=${offset}-` } : {},
      });
      logger.info('Fallback fetch response:', {
        url: fallbackUrl,
        resolvedUrl: response.url,
        resolvedHost: this._safeUrlHost(response.url),
        status: response.status,
        ok: response.ok,
        durationMs: Date.now() - startedAt,
      });
    } catch (error) {
      logger.error('Fallback fetch failed:', {
        url: fallbackUrl,
        error: error.message,
        code: error.code
      });
      throw error;
    }

    return response;
  }

  extractHuggingFaceRepo(url) {
    const match = /^https:\/\/huggingface\.co\/([^/]+\/[^/]+)\/resolve\/main\//i.exec(url);
    return match ? match[1] : null;
  }

  async resolveHuggingFaceFilename(repo, desiredFilename, signal) {
    try {
      logger.info('Resolving HuggingFace filename:', { repo, desiredFilename });
      const response = await this._fetchWithTimeout(`https://huggingface.co/api/models/${repo}`, { signal });
      if (!response.ok) {
        logger.warn('Failed to fetch HuggingFace model info:', response.status);
        return null;
      }
      const payload = await response.json();
      const siblings = Array.isArray(payload?.siblings) ? payload.siblings : [];
      const desiredLower = desiredFilename.toLowerCase();
      const exact = siblings.find((item) => typeof item?.rfilename === "string" && item.rfilename.toLowerCase() === desiredLower);
      if (exact?.rfilename) {
        logger.info('Found exact filename match:', exact.rfilename);
        return exact.rfilename;
      }
      const normalizedDesired = desiredLower.replace(/[-_.]/g, "");
      const fuzzy = siblings.find((item) => {
        const name = typeof item?.rfilename === "string" ? item.rfilename.toLowerCase() : "";
        return name.replace(/[-_.]/g, "") === normalizedDesired;
      });
      if (fuzzy?.rfilename) {
        logger.info('Found fuzzy filename match:', fuzzy.rfilename);
        return fuzzy.rfilename;
      }
      const desiredTokens = desiredLower
        .replace(/\.gguf$/i, "")
        .split(/[-_.]+/)
        .filter(Boolean);
      if (desiredTokens.length > 0) {
        const scored = siblings
          .map((item) => {
            const name = typeof item?.rfilename === "string" ? item.rfilename.toLowerCase() : "";
            if (!name.endsWith(".gguf")) {
              return null;
            }
            const tokens = name.replace(/\.gguf$/i, "").split(/[-_.\/]+/).filter(Boolean);
            let score = 0;
            for (const token of desiredTokens) {
              if (tokens.includes(token)) {
                score += 3;
              } else if (name.includes(token)) {
                score += 1;
              }
            }
            if (name.includes("q4") || name.includes("q4_k") || name.includes("q4_k_m")) {
              score += 2;
            }
            if (name.includes("instruct")) {
              score += 1;
            }
            return { filename: item.rfilename, score };
          })
          .filter(Boolean)
          .sort((a, b) => b.score - a.score);
        if (scored.length > 0 && scored[0].score > 0) {
          logger.info('Found scored filename match:', scored[0].filename, 'score:', scored[0].score);
          return scored[0].filename;
        }
      }
      const desiredExt = path.extname(desiredFilename).toLowerCase();
      if (desiredExt) {
        const byExtension = siblings.find((item) => {
          const name = typeof item?.rfilename === "string" ? item.rfilename : "";
          return name.toLowerCase().endsWith(desiredExt);
        });
        if (byExtension?.rfilename) {
          logger.info('Found extension match:', byExtension.rfilename);
          return byExtension.rfilename;
        }
      }
      logger.info('No filename resolution match found');
      return null;
    } catch (error) {
      logger.error('Error resolving HuggingFace filename:', error.message);
      return null;
    }
  }

  _computeRetryDelayMs(attempt) {
    const baseDelay = 2_000 * Math.pow(2, Math.max(0, attempt - 1));
    const jitter = Math.floor(Math.random() * 500);
    return baseDelay + jitter;
  }

  _isOptionalArtifactFilename(filename) {
    return OPTIONAL_ARTIFACT_FILENAMES.has(String(filename || "").toLowerCase());
  }

  _isRetryableDownloadError(error) {
    if (!error) {
      return false;
    }
    if (error.retryable === true) {
      return true;
    }
    if (typeof error.statusCode === "number") {
      return error.statusCode >= 500;
    }
    if (NETWORK_RETRYABLE_CODES.has(error.code)) {
      return true;
    }
    if (NETWORK_RETRYABLE_CODES.has(error.cause?.code)) {
      return true;
    }
    return error.name === "AbortError" || error.message === "fetch timed out";
  }

  _headersObject(headers) {
    if (!headers) {
      return {};
    }
    return Object.fromEntries(headers.entries());
  }

  _createDownloadError(message, context = {}, cause = null) {
    const error = new Error(message);
    Object.assign(error, context);
    if (cause) {
      error.cause = cause;
      if (!error.code && cause.code) {
        error.code = cause.code;
      }
    }
    return error;
  }

  _resolveArtifactTotalBytes(response, resumeOffset) {
    const contentRangeTotal = this._extractContentRangeTotal(response);
    if (contentRangeTotal > 0) {
      return contentRangeTotal;
    }
    const contentLength = Number(response.headers.get("content-length") || 0);
    if (contentLength > 0) {
      return response.status === 206 ? contentLength + resumeOffset : contentLength;
    }
    return 0;
  }

  _extractContentRangeTotal(response) {
    const contentRange = response?.headers?.get?.("content-range");
    if (!contentRange) {
      return 0;
    }
    const match = /bytes\s+(?:\d+-\d+|\*)\/(\d+)/i.exec(contentRange);
    return match ? Number(match[1]) : 0;
  }

  async _fetchWithTimeout(url, { signal, headers = {} } = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort(new Error("fetch timed out"));
    }, REQUEST_TIMEOUT_MS);
    const cleanup = [];

    if (signal) {
      const onAbort = () => controller.abort(signal.reason);
      signal.addEventListener("abort", onAbort, { once: true });
      cleanup.push(() => signal.removeEventListener("abort", onAbort));
    }

    try {
      return await fetch(url, {
        signal: controller.signal,
        headers: this._buildRequestHeaders(headers),
        redirect: "follow",
        dispatcher: this.fetchDispatcher || undefined,
      });
    } catch (error) {
      throw this._createDownloadError(
        `fetch failed for ${url}`,
        { url, headers, retryable: NETWORK_RETRYABLE_CODES.has(error?.code) || NETWORK_RETRYABLE_CODES.has(error?.cause?.code) },
        error,
      );
    } finally {
      clearTimeout(timeoutId);
      cleanup.forEach((fn) => fn());
    }
  }

  _buildRequestHeaders(headers = {}) {
    const merged = { ...headers };
    if (this.hfToken && !merged.Authorization) {
      merged.Authorization = `Bearer ${this.hfToken}`;
    }
    return merged;
  }

  _safeUrlHost(url) {
    try {
      return new URL(url).host;
    } catch (_error) {
      return null;
    }
  }

  async _streamArtifactToDisk({ response, tempPath, append, signal, onChunk }) {
    const writeStream = fs.createWriteStream(tempPath, {
      flags: append ? "a" : "w",
    });

    try {
      for await (const chunk of Readable.fromWeb(response.body, { signal })) {
        if (signal?.aborted) {
          throw signal.reason || new Error("download aborted");
        }
        const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
        if (!writeStream.write(buffer)) {
          await once(writeStream, "drain");
        }
        onChunk(buffer.byteLength);
      }
      await new Promise((resolve, reject) => {
        writeStream.end((error) => {
          if (error) {
            reject(error);
            return;
          }
          resolve();
        });
      });
      await this._fsyncFile(tempPath);
    } catch (error) {
      writeStream.destroy();
      throw this._createDownloadError(
        `streaming failed for ${tempPath}`,
        { partialBytes: fs.existsSync(tempPath) ? fs.statSync(tempPath).size : 0, retryable: this._isRetryableDownloadError(error) },
        error,
      );
    }
  }

  async _finalizeArtifact(tempPath, targetPath) {
    if (fs.existsSync(targetPath)) {
      fs.rmSync(targetPath, { force: true });
    }
    fs.renameSync(tempPath, targetPath);
  }

  async _fsyncFile(filePath) {
    const fileHandle = await fs.promises.open(filePath, "r+");
    try {
      await fileHandle.sync();
    } finally {
      await fileHandle.close();
    }
  }
}

module.exports = { ModelDownloadManager };
