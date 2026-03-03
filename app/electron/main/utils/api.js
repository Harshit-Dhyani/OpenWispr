// API utilities for backend communication
const state = require("../shared/state");

async function fetchBackendJson(apiPath, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const isRetryableGet = method === "GET";
  const timeoutMs = options.timeout || 30000;
  let response;
  let lastError = null;

  for (let attempt = 0; attempt < (isRetryableGet ? 5 : 1); attempt += 1) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      response = await fetch(`${state.API_ORIGIN}${apiPath}`, {
        headers: {
          "Content-Type": "application/json",
          ...(options.headers || {}),
        },
        ...options,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      break;
    } catch (error) {
      clearTimeout(timeoutId);
      lastError = error;

      if (error.name === 'AbortError') {
        lastError = new Error(`Request timeout after ${timeoutMs}ms`);
      }

      if (!isRetryableGet || attempt === 4) {
        throw lastError;
      }
      await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)));
    }
  }

  if (!response) {
    throw lastError || new Error("Failed to fetch");
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof payload === "string"
        ? payload
        : payload?.detail || payload?.error?.message || `HTTP ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

async function loadUserSettings() {
  return fetchBackendJson("/api/settings");
}

async function saveUserSettings(settings) {
  return fetchBackendJson("/api/settings", {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

async function loadDevicesForDesktop() {
  const result = await fetchBackendJson("/api/devices");
  return Array.isArray(result?.devices) ? result.devices : [];
}

module.exports = {
  fetchBackendJson,
  loadUserSettings,
  saveUserSettings,
  loadDevicesForDesktop,
};
