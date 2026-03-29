const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("openwisprQuickSettings", {
  getData: async () => {
    try {
      return await ipcRenderer.invoke("quick-settings:get-data");
    } catch (error) {
      console.error("[quickSettings:preload] getData failed:", error.message);
      throw error;
    }
  },
  update: async (settings) => {
    try {
      return await ipcRenderer.invoke("quick-settings:update", settings);
    } catch (error) {
      console.error("[quickSettings:preload] update failed:", error.message);
      throw error;
    }
  },
  openFullSettings: async () => {
    try {
      return await ipcRenderer.invoke("quick-settings:open-full");
    } catch (error) {
      console.error("[quickSettings:preload] openFullSettings failed:", error.message);
      throw error;
    }
  },
  close: async () => {
    try {
      return await ipcRenderer.invoke("quick-settings:close");
    } catch (error) {
      console.error("[quickSettings:preload] close failed:", error.message);
      throw error;
    }
  },
});
