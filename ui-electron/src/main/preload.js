const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("transcriptaDesktop", {
  getRuntimeInfo: () => ipcRenderer.invoke("app:get-runtime-info"),
  chooseDirectory: () => ipcRenderer.invoke("dialog:choose-directory"),
  requestBackend: (request) => ipcRenderer.invoke("backend:request", request)
});
