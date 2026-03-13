const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("openwisprQuickSettings", {
  getData: () => ipcRenderer.invoke("quick-settings:get-data"),
  update: (settings) => ipcRenderer.invoke("quick-settings:update", settings),
  openFullSettings: () => ipcRenderer.invoke("quick-settings:open-full"),
  close: () => ipcRenderer.invoke("quick-settings:close"),
});
