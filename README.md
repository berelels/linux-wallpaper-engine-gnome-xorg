# Linux Wallpaper Engine — GNOME + X11

Animated wallpapers from the Steam Workshop running natively on **GNOME Shell with X11** — including Zorin OS, Ubuntu, and any GNOME-based distro.

---

## Why this exists

The `linux-wallpaperengine` project can render Wallpaper Engine scenes on Linux, but on GNOME + X11 the standard `--screen-root` mode doesn't work. GNOME Shell renders its own background layer on top of the X11 root window, completely covering the wallpaper.

This project solves that by running the engine in `--window` mode with explicit monitor geometry, then using `wmctrl` to pin those windows below all other windows with `below + sticky` flags — making them behave exactly like a real wallpaper.

This approach, combined with a GUI for monitor selection and wallpaper properties, was developed and tested on **Zorin OS 17** (GNOME + X11) and is believed to be the first working solution for this specific combination.

---

## Requirements

### System
- Linux with **X11** session (not Wayland)
- **GNOME Shell** as desktop environment
- Tested on: **Zorin OS 17**, Ubuntu 24.04

> To check your session type: `echo $XDG_SESSION_TYPE` → must return `x11`

### Steam
- **Wallpaper Engine** purchased and in your Steam library
- Wallpaper Engine **installed via Steam with Proton** enabled — this downloads the `assets/` folder that the engine needs to render scenes
- At least one wallpaper subscribed on the **Steam Workshop**

> ⚠️ Installing Wallpaper Engine with Proton is the most commonly missed step. Without it, the `assets/` folder does not exist and nothing will work.

### linux-wallpaperengine
The open-source backend that renders the wallpapers. You need to compile it from source:

👉 https://github.com/Almamu/linux-wallpaperengine

Follow the build instructions in that repository before proceeding.

### System packages
```bash
sudo apt install zenity xrandr xdotool wmctrl python3
```

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/linux-wallpaper-engine-gnome-xorg
cd linux-wallpaper-engine-gnome
chmod +x install.sh
./install.sh
```

The installer will:
- Check and install missing dependencies
- Copy the script to `~/.local/bin/`
- Create an entry in your app menu
- Configure autostart for login
- Launch the setup wizard

---

## Usage

Search for **"Change Animated Wallpaper"** in your app menu and launch it.

### First run — Setup Wizard
You will be asked to:
1. Point to the `linux-wallpaperengine` binary
2. Point to your Steam root folder (auto-detected if possible)

This is saved to `~/.config/wallpaper-engine/config.sh` and won't be asked again.

### Every run — 4 steps
1. **Select monitors** — all connected monitors are listed with resolution and position, auto-detected via `xrandr`
2. **Select wallpaper** — lists all wallpapers downloaded from the Workshop by name
3. **Configure properties** — toggle boolean options specific to that wallpaper (mouse interaction, parallax, effects, etc.)
4. **Apply** — wallpaper is applied immediately and saved for autostart on next login

### Reconfigure paths
```bash
change-wallpaper.sh --setup
```

---

## How it works (technical)

### The GNOME compositor problem
On GNOME + X11, the `--screen-root` flag draws on the X11 root window. However, GNOME Shell's compositor renders its own background layer on top, making the wallpaper invisible. This is why standard tutorials don't work on Zorin OS / Ubuntu GNOME.

### The solution
Instead of `--screen-root`, we use `--window` with explicit geometry in the format `XxYxWxH`. This creates a normal application window positioned and sized to exactly cover each monitor.

After launch, `wmctrl` pins each window with:
```
below    → always behind all other windows
sticky   → visible on all workspaces
skip_taskbar + skip_pager → hidden from taskbar and overview
```

This makes the windows behave exactly like a real desktop wallpaper.

### Multiple monitors
The engine only accepts one `--window` per process. For multiple monitors, we launch one process per monitor with a 4-second delay between them. This prevents GPU context conflicts on AMD hardware (and likely on others as well).

### Autostart
Every time you apply a wallpaper, the script regenerates `~/.local/bin/start-wallpaper.sh` with the current settings. A `.desktop` file in `~/.config/autostart/` runs this script at login with a 5-second delay to let the desktop fully load first.

---

## File structure

```
~/.config/wallpaper-engine/config.sh    # Your paths (binary, Steam, assets)
~/.local/bin/change-wallpaper.sh        # Main script (this project)
~/.local/bin/start-wallpaper.sh         # Auto-generated autostart script
~/.config/autostart/wallpaper-engine.desktop
~/.local/share/applications/wallpaper-engine.desktop
```

---

## Known limitations

- **Wayland is not supported.** This solution relies on `xrandr`, `xdotool`, and `wmctrl`, which don't work on Wayland. For Wayland, `linux-wallpaperengine` has experimental `--layer` support but requires a completely different approach.
- **KDE Plasma** has its own native integration with `linux-wallpaperengine` and doesn't need this.
- **Scene-type wallpapers only.** Video wallpapers (`.mp4`) can be played with the Hanabi GNOME extension instead.
- **Rendering glitches** may appear on some wallpapers due to incomplete shader support in `linux-wallpaperengine`. This is a limitation of the backend, not this script.

---

## Credits

- [linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine) by Almamu — the engine that makes all of this possible
- Solution developed by **Gabriel Dias** on Zorin OS 17

---

## License

MIT
