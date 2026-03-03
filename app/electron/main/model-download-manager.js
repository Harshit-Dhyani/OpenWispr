const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

class ModelDownloadManager {
  constructor({ getApiOrigin, getUserDataPath, emit }) {
    this.getApiOrigin = getApiOrigin;
    this.getUserDataPath = getUserDataPath;
    this.emit = emit;
    this.downloads = new Map();
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

  async downloadModel(modelId) {
    if (this.downloads.has(modelId)) {
      return this.downloads.get(modelId).snapshot();
    }

    const catalogPayload = await this.getCatalog();
    const entry = (catalogPayload.catalog || []).find((item) => item.id === modelId);
    if (!entry) {
      throw new Error(`Unknown model: ${modelId}`);
    }

    const controller = new AbortController();
    const state = {
      modelId,
      status: "downloading",
      bytesDownloaded: 0,
      totalBytes: 0,
      progress: 0,
      speedBytesPerSec: 0,
      error: null,
      controller,
      snapshot() {
        return {
          model_id: this.modelId,
          status: this.status,
          bytes_downloaded: this.bytesDownloaded,
          total_bytes: this.totalBytes,
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
      fs.mkdirSync(installDir, { recursive: true });

      const startedAt = Date.now();
      let completedBytes = 0;
      let totalBytes = 0;

      for (const artifact of entry.download_artifacts || []) {
        const targetPath = path.join(installDir, artifact.filename);
        const response = await this.fetchArtifactResponse(entry, artifact, controller.signal);
        if (!response.ok || !response.body) {
          const detail = response ? `${response.status} ${response.statusText}` : "no response body";
          throw new Error(`Download failed for ${artifact.filename} (${detail})`);
        }

        const artifactTotal = Number(response.headers.get("content-length") || 0);
        totalBytes += artifactTotal;
        state.totalBytes = totalBytes;

        await new Promise((resolve, reject) => {
          const reader = response.body.getReader();
          const stream = fs.createWriteStream(targetPath);

          const pump = () =>
            reader.read().then(({ done, value }) => {
              if (done) {
                stream.end(resolve);
                return;
              }
              completedBytes += value.byteLength;
              state.bytesDownloaded = completedBytes;
              state.totalBytes = totalBytes || completedBytes;
              state.progress = state.totalBytes > 0 ? (completedBytes / state.totalBytes) * 100 : 0;
              const elapsedSeconds = Math.max((Date.now() - startedAt) / 1000, 0.1);
              state.speedBytesPerSec = completedBytes / elapsedSeconds;
              this.emit("model-download-progress", state.snapshot());
              stream.write(Buffer.from(value), (error) => {
                if (error) {
                  reject(error);
                  return;
                }
                pump();
              });
            }).catch(reject);

          stream.on("error", reject);
          pump();
        });

        const fileStat = fs.statSync(targetPath);
        if (fileStat.size < artifact.min_size_bytes) {
          throw new Error(`Verification failed for ${artifact.filename}: file too small`);
        }
        if (artifact.sha256) {
          const digest = await this.sha256File(targetPath);
          if (digest !== artifact.sha256) {
            throw new Error(`Verification failed for ${artifact.filename}: sha256 mismatch`);
          }
        }
      }

      state.status = "completed";
      state.progress = 100;
      this.emit("model-download-completed", state.snapshot());
      return state.snapshot();
    } catch (error) {
      if (controller.signal.aborted) {
        state.status = "cancelled";
        state.error = "cancelled";
        this.emit("model-download-cancelled", state.snapshot());
        return state.snapshot();
      }
      state.status = "failed";
      state.error = error instanceof Error ? error.message : String(error);
      this.emit("model-download-failed", state.snapshot());
      throw error;
    } finally {
      this.downloads.delete(modelId);
    }
  }

  cancelDownload(modelId) {
    const state = this.downloads.get(modelId);
    if (!state) {
      return { ok: false, error: "not-downloading" };
    }
    state.controller.abort();
    return { ok: true };
  }

  async removeModel(modelId) {
    const catalogPayload = await this.getCatalog();
    const entry = (catalogPayload.catalog || []).find((item) => item.id === modelId);
    if (!entry) {
      throw new Error(`Unknown model: ${modelId}`);
    }
    const installDir = path.join(this.getModelsRoot(), entry.category, entry.id);
    if (fs.existsSync(installDir)) {
      fs.rmSync(installDir, { recursive: true, force: true });
    }
    this.emit("model-removed", { model_id: modelId });
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

  async fetchArtifactResponse(entry, artifact, signal) {
    let response = await fetch(artifact.url, { signal });
    if (response.ok && response.body) {
      return response;
    }

    const repo = this.extractHuggingFaceRepo(artifact.url);
    if (!repo) {
      return response;
    }

    const resolvedFilename = await this.resolveHuggingFaceFilename(repo, artifact.filename, signal);
    if (!resolvedFilename || resolvedFilename === artifact.filename) {
      return response;
    }

    const fallbackUrl = `https://huggingface.co/${repo}/resolve/main/${resolvedFilename}?download=true`;
    response = await fetch(fallbackUrl, { signal });
    return response;
  }

  extractHuggingFaceRepo(url) {
    const match = /^https:\/\/huggingface\.co\/([^/]+\/[^/]+)\/resolve\/main\//i.exec(url);
    return match ? match[1] : null;
  }

  async resolveHuggingFaceFilename(repo, desiredFilename, signal) {
    try {
      const response = await fetch(`https://huggingface.co/api/models/${repo}`, { signal });
      if (!response.ok) {
        return null;
      }
      const payload = await response.json();
      const siblings = Array.isArray(payload?.siblings) ? payload.siblings : [];
      const desiredLower = desiredFilename.toLowerCase();
      const exact = siblings.find((item) => typeof item?.rfilename === "string" && item.rfilename.toLowerCase() === desiredLower);
      if (exact?.rfilename) {
        return exact.rfilename;
      }
      const normalizedDesired = desiredLower.replace(/[-_.]/g, "");
      const fuzzy = siblings.find((item) => {
        const name = typeof item?.rfilename === "string" ? item.rfilename.toLowerCase() : "";
        return name.replace(/[-_.]/g, "") === normalizedDesired;
      });
      if (fuzzy?.rfilename) {
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
          return byExtension.rfilename;
        }
      }
      return null;
    } catch {
      return null;
    }
  }
}

module.exports = { ModelDownloadManager };
