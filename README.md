# Linux Wallpaper Engine for GNOME

Browse Steam Workshop wallpapers and use them on your Linux desktop, with support for multiple monitors and clickable desktop icons.

**For Zorin 18 / Ubuntu 24.04, GNOME on X11, x86_64.** You need to own Wallpaper Engine and install it through Steam. Wallpaper compatibility varies; Wayland is not supported.

## Why this exists

[linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine) renders Wallpaper Engine scenes on Linux, but on GNOME with X11 its `--screen-root` mode does not work: GNOME Shell draws its own background over the X11 root window and hides the wallpaper.

This project runs the renderer in window mode on each monitor's exact geometry, marks those windows as desktop windows and keeps them below desktop icons and applications, so they behave like a real wallpaper. On top of that it connects the [Workshop browser](https://github.com/jagrat7/linux-wallpaper-engine) to the renderer, restores wallpapers at login and shows a still of them behind the Activities overview.

## Get started

```bash
git clone https://github.com/berelels/linux-wallpaper-engine-gnome-xorg.git
cd linux-wallpaper-engine-gnome-xorg
./run.sh
```

Run `./run.sh --check` first to check your system without installing anything.

Sign into Steam, install Wallpaper Engine (enable Proton if Steam asks), then select your Steam folder in the browser. Keep Steam running to browse and download Workshop wallpapers.

## What the installer does

`run.sh` runs as your normal user and asks for your sudo password once. It:

1. Installs build tools and libraries with `apt` (compiler, CMake, X11, OpenGL, SDL2, FFmpeg, mpv and PulseAudio development packages, plus `zenity`, `xdotool`, `wmctrl` and `python3-pil`).
2. Installs **Flatpak Steam** for your user if it is not installed yet. Native Steam is not used.
3. Downloads the Workshop browser **v0.4.11** and checks its SHA-256 before using it.
4. Clones the renderer at a pinned commit, applies [the GNOME fixes patch](patches/README.md) and builds it. The first build takes a while and needs several GB of disk space.
5. Patches the browser so closing it keeps the same session (a backup of `app.asar` is kept; the patch only applies to v0.4.11).
6. Installs the GNOME integration in `~/.local/share/wallpaper-engine-gnome` and adds three login helpers to `~/.config/autostart`:
   - `wallpaper-overview-sync`: updates the still image behind the overview. Idle when no wallpaper is playing.
   - `wallpaper-icon-stacking`: keeps wallpapers below desktop icons. Waits for X11 events.
   - `wallpaper-browser-restore`: starts your saved wallpapers at login, then exits.
7. Adds **Linux Wallpaper Engine**, **Wallpaper Position** and **Change Animated Wallpaper** to your app menu.

**Your GNOME background:** while wallpapers play on every monitor, the overview helper sets the GNOME background to a generated still (`~/.local/share/backgrounds/wallpaper-engine/overview-*.png`). Your original background is saved first in `~/.config/wallpaper-engine/original-background.json` and restored when playback stops, when only some monitors have a wallpaper, and on uninstall.

Nothing is sent anywhere. Network access is only used for `apt`, Flathub, the pinned browser download and the renderer source. Downloads, builds and logs are cached in `~/.cache/gnome-wallpaper-setup`. See [setup and troubleshooting](docs/SETUP.md) for every installed path.

## Everyday use

- Choose a wallpaper and click **Apply** for your selected display.
- Close with **X** to hide the browser while your wallpaper continues playing.
- Open **Linux Wallpaper Engine** again to return to the same session, without duplicate wallpaper or audio.
- Use the tray menu's **Quit** to exit, or **Stop** in the browser to stop a wallpaper.
- Use **Wallpaper Position** to adjust framing and zoom for each monitor.

Already installed? Close the browser using **Quit**, update your checkout, and rerun `./run.sh`. For a separately installed native browser, see [manual integration and session patch](docs/SESSION.md).

## Uninstall

Quit the browser from the tray menu, then remove the GNOME integration. This stops its helpers, restores your original background and removes its autostart and menu entries:

```bash
python3 ~/.local/share/wallpaper-engine-gnome/uninstall-browser-integration.py
```

To also remove the browser, renderer and caches:

```bash
rm -rf ~/.var/app/com.valvesoftware.Steam/data/gnome-wallpaper-suite ~/.cache/gnome-wallpaper-setup
rm -f ~/.local/share/applications/linux-wallpaper-engine-steam.desktop ~/.local/share/applications/wallpaper-engine.desktop
rm -f ~/.config/autostart/wallpaper-engine.desktop
rm -f ~/.local/bin/change-wallpaper.sh ~/.local/bin/run-wallpaper.sh ~/.local/bin/gnome-backend.py
```

If the installer replaced files you already had in `~/.local/bin` or `~/.local/share/applications`, your versions are kept next to them with a `.before-setup` suffix. Browser settings stay in `~/.config/Linux Wallpaper Engine` and launcher settings in `~/.config/wallpaper-engine`; delete them if you no longer need them. Flatpak Steam and the `apt` packages are left installed, since other software may use them.

## Credits and details

This release integrates [AbduL's](https://github.com/AbduLz0) and [zadwen's](https://github.com/zadwen/linux-wallpaper-engine-gnome-xorg) work, with their commit history, building on [Gabriel Dias / berelels](https://github.com/berelels/linux-wallpaper-engine-gnome-xorg). The browser is by [jagrat7](https://github.com/jagrat7/linux-wallpaper-engine); the renderer is by [Almamu](https://github.com/Almamu/linux-wallpaperengine). Original licenses and attribution are retained.

[Integration details](docs/INTEGRATION.md) · [Renderer patch](patches/README.md) · [Compatibility](COMPATIBILITY.md)

Tested live on Zorin OS 18.1 / GNOME 46 / X11. A fresh end-to-end installation and reboot have not been retested for this release.
