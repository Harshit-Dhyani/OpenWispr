/**
 * Quick settings controller script
 * Handles settings state, UI rendering, and IPC with main process.
 */
(function () {
  "use strict";

  const state = { settings: null, devices: [], languages: [], dirty: false };

  const statusText = document.getElementById("statusText");
  const appNameHeading = document.getElementById("appNameHeading");
  const hotkeyToggle = document.getElementById("hotkeyToggle");
  const hotkeySwitch = document.getElementById("hotkeySwitch");
  const pasteToggle = document.getElementById("pasteToggle");
  const pasteSwitch = document.getElementById("pasteSwitch");
  const languageSelect = document.getElementById("languageSelect");
  const deviceSelect = document.getElementById("deviceSelect");

  function setSwitch(node, input, checked) {
    input.checked = checked;
    node.dataset.on = checked ? "true" : "false";
  }

  function microphoneDevices(devices) {
    return devices.filter((device) => device.is_input && !(device.supports_loopback || device.is_loopback));
  }

  function render() {
    if (!state.settings) return;
    const hotkey = state.settings.hotkey || {};
    setSwitch(hotkeySwitch, hotkeyToggle, !!hotkey.enabled);
    setSwitch(pasteSwitch, pasteToggle, (hotkey.finish_mode_default || "finish_and_paste") === "finish_and_paste");

    languageSelect.innerHTML = "";
    for (const language of state.languages) {
      const option = document.createElement("option");
      option.value = language.code;
      option.textContent = language.label;
      option.selected = (hotkey.language || "auto") === language.code;
      languageSelect.appendChild(option);
    }

    deviceSelect.innerHTML = "";
    const defaultOption = document.createElement("option");
    defaultOption.value = "default";
    defaultOption.textContent = "Default microphone";
    deviceSelect.appendChild(defaultOption);

    for (const device of microphoneDevices(state.devices)) {
      const option = document.createElement("option");
      option.value = device.id;
      option.textContent = device.name;
      option.selected = (hotkey.device_id || "default") === device.id;
      deviceSelect.appendChild(option);
    }

    statusText.textContent = `Hotkey ${hotkey.enabled ? "enabled" : "disabled"} \u2022 ${hotkey.key_combination || "Ctrl+Shift+T"}`;
  }

  async function persist() {
    if (!state.settings) return;
    await window.openwisprQuickSettings.update(state.settings);
    state.dirty = false;
    render();
  }

  function updateHotkey(partial) {
    state.settings.hotkey = { ...(state.settings.hotkey || {}), ...partial };
    state.dirty = true;
    render();
    void persist();
  }

  hotkeyToggle.addEventListener("change", () => updateHotkey({ enabled: hotkeyToggle.checked }));
  pasteToggle.addEventListener("change", () =>
    updateHotkey({ finish_mode_default: pasteToggle.checked ? "finish_and_paste" : "finish" })
  );
  languageSelect.addEventListener("change", () => updateHotkey({ language: languageSelect.value }));
  deviceSelect.addEventListener("change", () => updateHotkey({ device_id: deviceSelect.value }));

  document.getElementById("openFullBtn").addEventListener("click", () =>
    window.openwisprQuickSettings.openFullSettings()
  );
  document.getElementById("doneBtn").addEventListener("click", () => window.openwisprQuickSettings.close());
  document.getElementById("closeBtn").addEventListener("click", () => window.openwisprQuickSettings.close());

  (async () => {
    const data = await window.openwisprQuickSettings.getData();
    const appName = data?.appName || "OpenWispr";
    document.title = `${appName} Quick Settings`;
    appNameHeading.textContent = appName;
    document.documentElement.dataset.theme = data?.settings?.general?.theme || "light";
    state.settings = data.settings;
    state.devices = data.devices || [];
    state.languages = data.languages || [];
    render();
  })().catch((error) => {
    statusText.textContent = error.message || "Failed to load quick settings.";
  });
})();
