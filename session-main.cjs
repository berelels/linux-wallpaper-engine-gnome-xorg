'use strict';
// GNOME integration: own one persistent browser session, including hidden windows.
const { app, BrowserWindow } = require('electron');
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
