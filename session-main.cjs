'use strict';
// GNOME integration: own one persistent browser session, including hidden windows.
const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const os = require('os');
const path = require('path');

// Applying a wallpaper runs `linux-wallpaperengine` from PATH: the GNOME adapter
// in the integration's bin folder. The launcher adds that folder, but the
// browser can also be started directly, as by its own "Launch on login" entry.
const adapterBin = process.env.LWE_ADAPTER_BIN || path.join(
  process.env.XDG_DATA_HOME || path.join(os.homedir(), '.local/share'), 'wallpaper-engine-gnome/bin');
const searchPath = (process.env.PATH || '').split(path.delimiter);
if (fs.existsSync(path.join(adapterBin, 'linux-wallpaperengine')) && !searchPath.includes(adapterBin)) {
  process.env.PATH = [adapterBin, ...searchPath].join(path.delimiter);
}
// That entry names the browser executable itself, so at login the overview and
// icon helpers never started. Point it at the integration launcher instead.
const loginExec = process.env.LWE_LOGIN_EXEC;
if (loginExec) {
  const writeFileSync = fs.writeFileSync;
  fs.writeFileSync = function (file, data, ...rest) {
    if (typeof file === 'string' && typeof data === 'string'
        && path.basename(path.dirname(file)) === 'autostart'
        && data.includes('Comment=Launch Linux Wallpaper Engine on startup')) {
      data = data.replace(/^Exec=.*$/m, () => 'Exec=' + loginExec);
    }
    return writeFileSync.call(this, file, data, ...rest);
  };
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  let quitting = false;
  const reveal = () => {
    const window = BrowserWindow.getAllWindows().find(w => !w.isDestroyed());
    if (!window) {
      app.once('browser-window-created', (_event, created) => {
        created.once('ready-to-show', () => { created.show(); created.focus(); });
      });
      return;
    }
    if (window.isMinimized()) window.restore();
    window.show();
    window.focus();
  };
  app.on('second-instance', reveal);
  app.on('before-quit', () => { quitting = true; });
  app.on('browser-window-created', (_event, window) => {
    window.on('close', event => {
      if (!quitting) {
        event.preventDefault();
        window.hide();
      }
    });
  });
  require('./.vite/build/main.js');
}
