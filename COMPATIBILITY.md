# Compatibility verification — 21 October 2026

Retested all 48 wallpapers previously marked red or yellow in this PC’s browser. All 48 produced nonblank frames with the installed patched renderer. 31 had no recorded diagnostic; 17 retained warnings or unsupported-feature diagnostics. The browser ratings were refreshed from these results.

These were 640×360 previews observed over several seconds, with process-lifetime and changing-frame checks. Two X11 enumeration races were retried successfully. This does not verify every effect at full desktop resolution or establish visual parity with Windows. A synthetic gradient verified live horizontal/vertical framing at 200% zoom. A scene fixture verified property values and timer callbacks.

## Previously broken entries

| Wallpaper | Result |
|---|---|
| [Black & White Tree](https://steamcommunity.com/sharedfiles/filedetails/?id=3387640151) | Displays; diagnostics remain |
| [A Solitary Reflection [4K]](https://steamcommunity.com/sharedfiles/filedetails/?id=3644280276) | Displays without recorded diagnostics |
| [Black and White](https://steamcommunity.com/sharedfiles/filedetails/?id=3042527971) | Displays without recorded diagnostics |
| [Colorful Fluid Animation [Audio Responsive]](https://steamcommunity.com/sharedfiles/filedetails/?id=1748506393) | Displays; diagnostics remain |
| [Evangelion asuka langley soryu vol.1](https://steamcommunity.com/sharedfiles/filedetails/?id=2051445900) | Displays without recorded diagnostics |
| [Jujutsu Kaisen: Gojo x Sukuna \| Anime Quotes \| 両面宿儺 x  五条悟 \|](https://steamcommunity.com/sharedfiles/filedetails/?id=3277650572) | Displays; diagnostics remain |
| [Mount Fuji and Lake Kawaguchi \| Japan](https://steamcommunity.com/sharedfiles/filedetails/?id=3618078338) | Displays; diagnostics remain |
| [Toji \| jujutsu kaisen](https://steamcommunity.com/sharedfiles/filedetails/?id=3173180645) | Displays without recorded diagnostics |
| [White Tree - Snow](https://steamcommunity.com/sharedfiles/filedetails/?id=1789171537) | Displays; diagnostics remain |
| [剑来·剑灵 \| 4K](https://steamcommunity.com/sharedfiles/filedetails/?id=3748682389) | Displays; diagnostics remain |

## Remaining limitations

Some wallpapers still report unsupported puppet model versions, light/volume-light layers, custom shader metadata/effects, or text-script imports. Web wallpapers can also report GTK/OpenGL and NSS diagnostics, and authored JavaScript dependencies may be incomplete. These diagnostics remain visible; they were not suppressed to turn a rating green.

The web audio bridge currently mirrors the native recorder’s single spectrum into two channels. The fluid wallpaper is interactive and can fade toward black without mouse movement or audio.

The installed runtime is kept separate from the build tree so later compilation cannot overwrite libraries in running wallpapers. Source changes are reproducible using `patches/backend-base.txt` and `patches/backend-fixes.patch`. Workshop downloads and user selections are preserved.

## Desktop/session validation

44 integration tests and 15 native test cases passed. Live checks verified game
pause at 0% renderer CPU and resumed changing frames after Hollow Knight exited,
repeated restoration without duplicate players, and parent-death cleanup even
when a child is suspended. The position dialog was rendered and inspected.
At final desktop validation only HDMI-0 was active; the saved DP-0 selection was
retained and disconnected-monitor startup was covered by a regression test.
