# Persistent browser session

The supported browser is jagrat7/linux-wallpaper-engine **v0.4.11**, in its native Linux ZIP layout. `run.sh` applies the patch automatically to its private copy. This is a local integration patch, not an upstream browser release.

For an existing native installation, use the tray's **Quit** first, then:

```bash
python3 patch-browser-session.py /path/to/browser/resources/app.asar
python3 install-browser-integration.py \
  --backend /path/to/patched/linux-wallpaperengine \
  --browser /path/to/browser/linux-wallpaper-engine
```

The archive must be writable by your user. The patch retains `app.asar.before-persistent-session`, preserves native modules, and refuses unsupported browser versions. Enable the browser's system tray setting so **Quit** remains accessible. Use the installed app-menu shortcut consistently; launching with a different HOME or XDG profile represents a different session.

X hides the window. Launching again signals the existing Electron instance to show itself before a second instance can initialize wallpapers. The launcher cleans up its own renderer process group when the browser actually exits. It does not kill unrelated players.

To undo the browser patch, quit the app and restore the backup over `app.asar`. Reinstalling/upgrading the browser can replace this patch; the patcher only supports v0.4.11. The older Flatpak browser runtime scripts in `setup/` are retained for history but are no longer used by `run.sh`.

## Checks

```bash
python3 -m unittest discover -v
node test-session.cjs
bash -n run.sh install.sh change-wallpaper.sh run-wallpaper.sh
```

The Electron lifecycle test covers secondary startup, close-to-hide, restoring the same window, and explicit quit. Archive tests cover idempotence, backups, payload preservation and rejecting unsupported versions. Live close/reopen checks were performed on the maintainer's installed app; the complete installer still needs a clean-machine test.
