# Setup & troubleshooting

[← Back to the quick start](../README.md)

## Before installing

`run.sh` supports **Zorin OS 18 / Ubuntu 24.04 (noble), GNOME on X11, x86_64**. It does not support Wayland, ARM, or other distributions.

Check your session with:

```bash
echo "$XDG_SESSION_TYPE"
```

It must say `x11`. You can also run `./run.sh --check` to check the platform without installing anything.

Close an already-running Workshop browser before setup. You need internet, several GB of free disk space, and permission to install system packages using `sudo`.

## Steam asks me to install Wallpaper Engine

You must own Wallpaper Engine. The installer opens Steam’s installation page, but you complete Steam sign-in and installation yourself. If Install is unavailable, open the game’s **Properties → Compatibility** and enable **Proton Experimental**. Wait for the download to finish, then click **Check installation** in the setup dialog.

The suite uses **Flatpak Steam**, even if native Steam is already installed. Native Steam assets are not copied automatically. External Steam libraries are detected, but must already be accessible to Flatpak Steam. The installer does not grant broad filesystem permissions, buy the game, or collect credentials.

## Installation stopped

Read the error and rerun:

```bash
./run.sh
```

Downloads and build progress are cached. Logs are saved in `~/.cache/gnome-wallpaper-setup` (or under `$XDG_CACHE_HOME` if set). Include the relevant error when reporting an issue; remove personal information first.

The build uses two jobs by default. To change this:

```bash
BUILD_JOBS=4 ./run.sh
```

More jobs can speed up compilation but use more memory. Run `./run.sh --help` for the available options.

## Where files are installed

| Item | Location |
| --- | --- |
| Browser, renderer, and runtime helpers | `~/.var/app/com.valvesoftware.Steam/data/gnome-wallpaper-suite` |
| Downloads, build cache, and setup logs | `~/.cache/gnome-wallpaper-setup` |
| Standalone launcher and monitor helper | `~/.local/bin` |
| Standalone launcher configuration | `~/.config/wallpaper-engine/config.sh` |
| Application menu entries | `~/.local/share/applications` |
| Standalone launcher startup entry | `~/.config/autostart/wallpaper-engine.desktop` |

Existing browser settings are preserved except for the assets path and the backend execution/window-mode settings needed for integration. Backups are saved before these updates.

The setup pins browser version **v0.4.11** and renderer commit **b016d7d1fdcf4e5fd2f9c9fa420a8aaa07fee02d**. It verifies the browser download’s SHA-256, builds the renderer with its submodules, and checks missing libraries inside Steam’s running environments. Re-run setup if a Steam runtime update introduces missing dependencies.

## The separate “Change Animated Wallpaper” launcher

This menu entry applies already-downloaded wallpapers without using the browser. Select your monitors, choose a wallpaper, and confirm any properties. Applying through this selector saves a startup script to restore that selection at login.

To prevent the saved wallpaper from starting at login, disable **Wallpaper Engine Autostart** in **Startup Applications**. Login restoration has not yet been verified through a logout/login test on the tested setup.

The older `./install.sh` installs only this standalone selector. Advanced users who choose it must supply their own backend and dependencies; use `./run.sh` for complete setup.

## A wallpaper doesn’t render correctly

Community wallpapers use different features, and backend compatibility varies. Try another wallpaper to distinguish an item-specific rendering problem from a setup problem. Video playback has been confirmed; this does not establish support for every scene or web wallpaper.

If a player is stuck, this stops the backend processes:

```bash
pkill -f '(^|/)linux-wallpaperengine( |$)'
```

## How the GNOME fixes work

GNOME can cover wallpapers drawn on the X11 root window. Our adapter converts the browser’s monitor requests into separate borderless player windows. It waits for each window by process ID, marks it as a desktop surface, positions it on the selected monitor, and lowers it beneath the icon layer.

Both `above` and `below` window-state flags are removed: in the tested GNOME setup, combining the desktop type with `below` left the wallpaper above desktop icons. A separate X11 restack request provides the correct ordering. The adapter also terminates its renderer children when the browser stops it, including a forced stop.

For manual integration, `gnome-backend.py` accepts the real renderer executable followed by its usual arguments:

```bash
python3 gnome-backend.py /path/to/real/linux-wallpaperengine \
  --screen-root HDMI-0 --screen-root HDMI-1-2 \
  --assets-dir /path/to/wallpaper_engine/assets --bg /path/to/workshop/item
```

Monitor names vary. A wrapper named `linux-wallpaperengine` can connect this adapter to a browser that discovers the backend on PATH. Point it to the **real** renderer, never back to itself. Python 3, xrandr, xprop, wmctrl, and their libraries must exist in the browser’s execution environment. `run.sh` handles this for its supported configuration.

## What has been verified

- Visible video playback on two monitors on Zorin OS 18.1 / GNOME 46 / X11.
- Desktop icons remain visible and clickable; normal application windows stay above the wallpaper.
- Browser Apply starts both players; Stop removes both windows and playback processes.
- Shell validation, nine automated tests, dependency package resolution, and execution of the generated backend wrapper in both live Steam runtimes.

A full installation on a fresh machine and logout/login restoration are **not yet verified**. Please include your distribution, session type, wallpaper type, and relevant log output in [bug reports](https://github.com/AbduLz0/linux-wallpaper-engine-gnome-xorg/issues).
