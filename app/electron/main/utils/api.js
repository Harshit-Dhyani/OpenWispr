// API utilities for backend communication
const state = require("../shared/state");

async function fetchBackendJson(apiPath, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const isRetryableGet = method === "GET";
  const timeoutMs = options.timeout || 30000;
  let response;
  let lastError = null;
  const headers = { ...(options.headers || {}) };

  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  for (let attempt = 0; attempt < (isRetryableGet ? 5 : 1); attempt += 1) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      response = await fetch(`${state.API_ORIGIN}${apiPath}`, {
        headers,
        ...options,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      state.backendReady = true;
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
  try {
    const settings = await fetchBackendJson("/api/settings");
    state.cachedSettings = settings;
    return settings;
  } catch (error) {
    if (state.cachedSettings) {
      return state.cachedSettings;
    }
    throw error;
  }
}

async function saveUserSettings(settings) {
  const payload = await fetchBackendJson("/api/settings", {
    method: "POST",
    body: JSON.stringify(settings),
  });
  state.cachedSettings = payload;
  return payload;
}

async function loadDevicesForDesktop() {
  try {
    const result = await fetchBackendJson("/api/devices");
    const devices = Array.isArray(result?.devices) ? result.devices : [];
    state.cachedDevices = devices;
    return devices;
  } catch (error) {
    if (Array.isArray(state.cachedDevices) && state.cachedDevices.length > 0) {
      return state.cachedDevices;
    }
    throw error;
  }
}

module.exports = {
  fetchBackendJson,
  loadUserSettings,
  saveUserSettings,
  loadDevicesForDesktop,
};
