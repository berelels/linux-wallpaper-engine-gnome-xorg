# Renderer fixes used by this integration

The position dialog needs the accompanying renderer patch; an unmodified renderer
will ignore the saved framing settings. The patch also accepts vector text padding,
allows invalid optional JSON values to propagate as errors, keeps command-line
argument storage alive for Chromium, and fixes CEF loader ordering.

Base: Almamu/linux-wallpaperengine; see `backend-base.txt` for the exact commit.
`backend-fixes.patch` contains the changes without third-party source or binaries.

Apply in a checkout at that commit, then initialize its submodules and build using
its documented native dependencies:

```
git apply /path/to/this/repo/patches/backend-fixes.patch
git submodule update --init --recursive
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DBUILD_TESTING=ON
cmake --build build -j 6
```

Point the integration installer at `build/output/linux-wallpaperengine` (retain
that build directory), or use the renderer's normal CMake installation procedure.
The renderer reads `WE_POSITION_FILE` and `WE_POSITION_MONITOR`, supplied by the
GNOME adapter. It rereads saved position settings four times per second; defaults
are centered at 100% zoom. It adjusts texture coordinates, not desktop window
position, so the wallpaper continues to fill its monitor and stays below icons.

## Covered fixes

- Parse vector text padding and nullable layer metadata without crashing.
- Accept trailing commas in JSON assets while preserving embedded scripts.
- Read camera preview settings through their user-property bindings.
- Initialize translated shader temporaries and normalize const function returns.
- Prevent a zero-opacity overlay from covering the scene.
- Keep scene text scripts connected to engine properties and timers; retain timer
  callbacks correctly and allow cancellation while a callback runs.
- Correct CEF subprocess initialization, loader/resource paths, OpenBLAS thread
  settings (in the adapter), GLX/OpenGL ordering, and offscreen texture upload.
- Honor the web frame-rate limit and create web views at their final dimensions.
- Deliver web properties and audio callbacks. The current native recorder exposes
  a single spectrum; it is mirrored into the two web audio channels.

Some scene features and graphics-driver diagnostics remain outside these fixes.
A wallpaper displaying frames is not proof that every effect matches Windows.
