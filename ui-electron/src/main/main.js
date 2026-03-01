const path = require("node:path");
const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");

const API_ORIGIN = process.env.TRANSCRIPTA_API_ORIGIN || "http://127.0.0.1:8765";

let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 960,
    minWidth: 1180,
    minHeight: 760,
    backgroundColor: "#09131b",
    title: "Transcripta",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  mainWindow.loadFile(path.join(__dirname, "..", "renderer", "index.html"));

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

ipcMain.handle("app:get-runtime-info", () => ({
  apiOrigin: API_ORIGIN,
  platform: process.platform,
  versions: process.versions
}));

ipcMain.handle("dialog:choose-directory", async () => {
  const result = await dialog.showOpenDialog(mainWindow ?? undefined, {
    title: "Choose export folder",
    properties: ["openDirectory", "createDirectory"]
  });

  if (result.canceled || result.filePaths.length === 0) {
    return null;
  }

  return result.filePaths[0];
});

ipcMain.handle("backend:request", async (_event, request) => {
  const { method = "GET", path: apiPath = "/", body, headers = {} } = request ?? {};

  if (typeof apiPath !== "string" || !apiPath.startsWith("/")) {
    return {
      ok: false,
      status: 400,
      error: "API path must start with /"
    };
  }

  try {
    const response = await fetch(`${API_ORIGIN}${apiPath}`, {
      method,
      headers: {
        Accept: "application/json",
        ...headers,
        ...(body ? { "Content-Type": "application/json" } : {})
      },
      body: body ? JSON.stringify(body) : undefined
    });

    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json")
      ? await response.json()
      : await response.text();

    return {
      ok: response.ok,
      status: response.status,
      data: payload
    };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      error: error instanceof Error ? error.message : "Unknown backend error"
    };
  }
});
