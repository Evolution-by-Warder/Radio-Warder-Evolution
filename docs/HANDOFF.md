# Radio Warder Evolution — test12 release

Source: `28a40b067935ba9793811d2c57a13c5946f962da`.
CI: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41628526134 — success, including both public package downloads and feed publication.

## Current behaviour

- Plugin browser and extensions menu: Radio Warder Evolution.
- Canonical opkg identity: enigma2-plugin-extensions-radio-warder-evolution. Conflicts/Replaces the old enigma2-plugin-extensions-warderradio, with the same owned runtime files and unchanged user state path. Direct installation of the test12 IPK performs this transition in one opkg operation.
- LEFT menu ends with Settings, Update. Footer has the original four colour controls. INFO is an alternate manual update shortcut.
- RIGHT from any station or UP from the first row immediately opens country choices. White Select country stays unchanged; only the cyan country receives the focus pointer. Cancel preserves station/scroll position and audio.
- The former cyan Canvas animation is replaced with the exact 48 approved FullHDGlass transparent spectrum frames: 84 fine multicolour segmented columns and peaks. Native Pixmap, one paint per 100 ms, lazy shared cache bounded at 8,467,200 decoded pixel bytes. It pauses when hidden, hides while idle and disables itself on an unavailable frame without affecting playback. No audio analysis or per-segment GUI drawing. The original 350x126 aspect ratio is retained in the player panel.
- Last-station resume, 21 languages (67 complete strings), catalogue, picons, favourites, history and optional recording remain.
- After a verified in-plugin installation, a localized INFO message lasts three seconds and automatically restarts the GUI. The initial installation approval remains. Failure restores controls and never schedules restart. Repeated completion callbacks cannot restart twice.

## Package migration feeds

Installed old updaters validate the old package name and exact release URL. The immutable test11 bridge is therefore still served by update/testing.json. It carries the same new features, retains the old opkg identity, and embeds the v2 updater. After GUI restart it offers canonical test12 from update/v2/testing.json. Installing the renamed test12 IPK directly bypasses this extra compatibility step. The v2 stable feed is empty; other products' production feeds are untouched. Older FullHDGlass-hosted radio test builds still migrate through the previously published test8 bridge before reaching the dedicated repository.

Canonical test12: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.0-test12/enigma2-plugin-extensions-radio-warder-evolution_0.1.0-test12_all.ipk
SHA-256 `5697273f0713631b91a20f923dd014eae68dce15928098619055cbe0da22e7b5`; 3045420 bytes.
Bridge test11: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.0-test11/enigma2-plugin-extensions-warderradio_0.1.0-test11_all.ipk
SHA-256 `65f7238e6953b05465e3f707a13f226ca70050c660198efa1f34415166a059c5`; 3045392 bytes.

31 unit cases plus 15 native cases on each of three pinned OpenPLi/OpenATV revisions: 76 executions. Tests include the actual frozen old updater accepting/verifying the bridge, the v2 updater accepting the renamed payload, controls containing both migration fields, frame hashes/PNG format, bounded cache, hidden/idle lifecycle, safe failure, ping-pong continuity, descriptor names and restart behaviour. IPK scope/Python 3.9/install-script verification passed. CI independently downloaded and checked both public packages; connector asset digests/sizes also match both published feeds. Real receiver package-manager migration and visual confirmation remain to be tested by the user; C++/OS boundary is stubbed in native replay.

Test10 automatic restart source was `e27fa6c51c8c6120ae72483c32ee14f26f380f38`, CI https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41626857539 — success. Superseded by test12 and the test11 compatibility bridge.

The user set the repository About description to Warder Radio - World of Radio Stations; this matches the approved branding. No further About edit was requested.
