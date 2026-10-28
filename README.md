# Linux Wallpaper Engine for GNOME

Browse Steam Workshop wallpapers and use them on your Linux desktop, with support for multiple monitors and clickable desktop icons.

**For Zorin 18 / Ubuntu 24.04, GNOME on X11, x86_64.** You need to own Wallpaper Engine and install it through Steam. Wallpaper compatibility varies; Wayland is not supported.

## Get started

```bash
git clone https://github.com/AbduLz0/linux-wallpaper-engine-gnome-xorg.git
cd linux-wallpaper-engine-gnome-xorg
./run.sh
```

Setup installs dependencies, downloads the browser, builds the patched renderer, and adds **Linux Wallpaper Engine** to your app menu. The first build takes time and needs internet, several GB of disk space, and your sudo password.

Sign into Steam, install Wallpaper Engine (enable Proton if Steam asks), then select your Steam folder in the browser. Keep Steam running to browse and download Workshop wallpapers.

## Everyday use

- Choose a wallpaper and click **Apply** for your selected display.
- Close with **X** to hide the browser while your wallpaper continues playing.
- Open **Linux Wallpaper Engine** again to return to the same session, without duplicate wallpaper or audio.
- Use the tray menu's **Quit** to exit, or **Stop** in the browser to stop a wallpaper.
- Use **Wallpaper Position** to adjust framing and zoom for each monitor.

Already installed? Close the browser using **Quit**, update your checkout, and rerun `./run.sh`. For a separately installed native browser, see [manual integration and session patch](docs/SESSION.md).

## Credits and details

This release integrates [zadwen’s improvements](https://github.com/zadwen/linux-wallpaper-engine-gnome-xorg) with their commit history, building on [Gabriel Dias / berelels](https://github.com/berelels/linux-wallpaper-engine-gnome-xorg). The browser is by [jagrat7](https://github.com/jagrat7/linux-wallpaper-engine); the renderer is by [Almamu](https://github.com/Almamu/linux-wallpaperengine). Original licenses and attribution are retained.

[Integration details](docs/INTEGRATION.md) · [Renderer patch](patches/README.md) · [Compatibility](COMPATIBILITY.md)

Tested live on Zorin OS 18.1 / GNOME 46 / X11. The session fix was checked through three close/reopen cycles, rapid double launch, and a legacy shortcut, preserving the same browser and renderer processes. A fresh end-to-end installation and reboot have not been retested for this release.
