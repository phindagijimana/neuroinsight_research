/**
 * preload — secure bridge between the renderer and the main process.
 *
 * Exposes a minimal `window.nir` API over contextBridge. The renderer has no
 * direct Node or ipcRenderer access (contextIsolation + nodeIntegration:false).
 */
const { contextBridge, ipcRenderer } = require("electron");

const invoke = (channel, ...args) => ipcRenderer.invoke(channel, ...args);

contextBridge.exposeInMainWorld("nir", {
  preflight: {
    run: () => invoke("preflight:run"),
  },
  platform: {
    summary: () => invoke("platform:summary"),
  },
  backend: {
    start: () => invoke("backend:start"),
    stop: () => invoke("backend:stop"),
    stopAll: () => invoke("backend:stopAll"),
    status: () => invoke("backend:status"),
    runtime: () => invoke("backend:runtime"),
    openUI: () => invoke("backend:openUI"),
  },
  ui: {
    control: () => invoke("ui:control"),
  },
  shell: {
    openExternal: (url) => invoke("shell:openExternal", url),
  },
  settings: {
    get: () => invoke("settings:get"),
    update: (patch) => invoke("settings:update", patch),
  },
  license: {
    status: () => invoke("license:status"),
    enforcement: () => invoke("license:enforcement"),
    importText: (text) => invoke("license:importText", text),
    importFile: () => invoke("license:importFile"),
  },
  lock: {
    status: () => invoke("lock:status"),
    enable: (pin) => invoke("lock:enable", pin),
    disable: (pin) => invoke("lock:disable", pin),
    unlock: (pin) => invoke("lock:unlock", pin),
    lockNow: () => invoke("lock:lockNow"),
  },
  creds: {
    status: () => invoke("creds:status"),
    set: (name, value) => invoke("creds:set", name, value),
    get: (name) => invoke("creds:get", name),
    delete: (name) => invoke("creds:delete", name),
  },
  diagnostics: {
    export: () => invoke("diagnostics:export"),
    reveal: (filePath) => invoke("diagnostics:reveal", filePath),
  },
});
