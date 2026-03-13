const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("nirDesktop", {
  getStatus: () => ipcRenderer.invoke("nir:getStatus"),
  startBackend: () => ipcRenderer.invoke("nir:startBackend"),
  stopBackendApp: () => ipcRenderer.invoke("nir:stopBackendApp"),
  stopBackendAll: () => ipcRenderer.invoke("nir:stopBackendAll"),
  openAppInMainWindow: () => ipcRenderer.invoke("nir:openAppInMainWindow"),
  openControlCenter: () => ipcRenderer.invoke("nir:openControlCenter"),
  getDesktopSettings: () => ipcRenderer.invoke("nir:getDesktopSettings"),
  updateDesktopSettings: (patch) => ipcRenderer.invoke("nir:updateDesktopSettings", patch),
  getDesktopPaths: () => ipcRenderer.invoke("nir:getDesktopPaths"),
  runPreflight: () => ipcRenderer.invoke("nir:runPreflight"),
  exportDiagnostics: () => ipcRenderer.invoke("nir:exportDiagnostics"),
  getLicenseStatus: () => ipcRenderer.invoke("nir:getLicenseStatus"),
  importLicenseText: (text) => ipcRenderer.invoke("nir:importLicenseText", text),
  importLicenseFile: () => ipcRenderer.invoke("nir:importLicenseFile"),
  getCredentialStoreStatus: () => ipcRenderer.invoke("nir:getCredentialStoreStatus"),
  saveSecret: (key, value) => ipcRenderer.invoke("nir:saveSecret", key, value),
  loadSecret: (key) => ipcRenderer.invoke("nir:loadSecret", key),
  deleteSecret: (key) => ipcRenderer.invoke("nir:deleteSecret", key),
});
