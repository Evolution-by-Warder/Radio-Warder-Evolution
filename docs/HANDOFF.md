# Radio Warder Evolution — test15 navigation correction

User confirmed on the receiver that the plugin name Radio Warder Evolution and playing-song text now work in test14. Their screenshot also confirms the cyan panel outlines and multicolour spectrum are visible. They reported UP from the first left-menu item incorrectly opened country choices.

Fixed the UP condition to apply the country shortcut only when focus is the centre station list. Left-menu UP/DOWN now wrap and move solely inside its six function entries, including first-to-last and last-to-first. RIGHT from the left still returns to the same selected station. Centre UP from its first row and RIGHT from any station still open country choices immediately. No layout, metadata, naming or updater changes.

Source: `cadedbcf419fb1e3fc458897a18ae341024c16cb`.
CI: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41631505922 — success.
36 unit cases plus 17 native cases on each of three pinned OpenPLi/OpenATV revisions: 87 executions. The new regression cycles the entire left menu in both directions, checks there is no country dialog, and verifies station position/playback are preserved, then checks the centre shortcut. Package/Python/install-script validation passed. CI downloaded and verified public IPKs and advanced the v2 test feed; connector release asset digest/size match the live feed. Physical confirmation of the left-menu fix remains pending.

Latest IPK: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.0-test15/enigma2-plugin-extensions-radio-warder-evolution_0.1.0-test15_all.ipk
SHA-256 `22f8e7c57ff49375018f3ec8bd23869a54c997c20abaa0f8c16bd38a65d46dc4`; 3047892 bytes.

---

Prior release records follow.

# Radio Warder Evolution — test14 metadata correction

User requires ICY as the primary source because this plugin plays internet-radio streams. Implemented that exact priority: ICY StreamTitle from the playing URL first; native Enigma2 artist/title tags only while ICY is absent, unavailable or pending. The reader and separator repair come from the existing FullHDGlass radio implementation. A standalone ICY announcement remains current display text even without a separate artist.

One bounded daemon worker per screen probes at most once per 15 seconds for a station; only the GUI timer paints returned text. Reads use Icy-MetaData: 1, 3-second socket timeout, a six-second read deadline and a maximum 256 KiB metadata interval. There are no GUI/network calls on the same thread. Station changes, stop/end/failure and close invalidate old results; late replies cannot display under the next station. The audio service itself is untouched. Streams with no ICY/native title retain No track information. Actual receiver confirmation of broadcaster metadata remains pending; tests use fragmented protocol fixtures and controlled asynchronous reads, not claims of a live stream audit.

The user's screenshot still showed Warder Radio. The previously published test13 IPK was opened and its digest checked against the public asset: both PluginDescriptor entries already say Radio Warder Evolution. The screenshot alone does not establish installed version, cached in-memory descriptor or cause. Test14 postinst clears only this plugin's .pyc/.pyo cache, retaining settings; successful in-plugin updates restart GUI automatically after the existing three-second notice. A manual opkg installation still needs a GUI restart. Canonical opkg identity remains enigma2-plugin-extensions-radio-warder-evolution.

Source: `70264a512d399447e67832629e5fed0ec41d7184`.
CI: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41630197919 — success.
36 unit cases plus 16 native cases on each of three pinned OpenPLi/OpenATV revisions: 84 executions, plus IPK and install-script validation. Tests cover primary ICY/native fallback priority, absent song data, callbacks after station changes/close, 15-second throttling, one worker, failed reads, bounds/deadline, fragmented reads, UTF-8/legacy text, announcement/separator handling and unchanged plugin descriptors. Both metadata.py and spectrum.py are now required by post-install payload verification.

Latest IPK: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.0-test14/enigma2-plugin-extensions-radio-warder-evolution_0.1.0-test14_all.ipk
SHA-256 `5a15bfe1a64295430dbce1f73bb806e0b57cf480d99a039838e07b0c00707d05`; 3047842 bytes. CI verified public download/size/hash and updated v2 testing feed. Connector metadata independently matches. The immutable test11 old-ID bridge is unchanged and leads to test14; stable feeds remain empty.

---

Previous release records follow; the native-metadata-only behaviour before test14 is superseded above.

# Radio Warder Evolution — test13

All three main panels now have a thin cyan outline in the PiconHub/Warder style. Geometry and controls are retained. Native opaque borders are drawn above the panel fills and below live text, with width scaled from 2 px at Full HD.

Source: `f7637a9cdb59eca2f517e2df09daae0caef9db43`.
CI: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41628985504 — success. All 76 existing cases and IPK validation passed. The public package was downloaded and size/SHA-256 verified in CI; connector release metadata matches the live v2 feed. The test11 old-ID bridge remains byte-identical.

Latest IPK: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.0-test13/enigma2-plugin-extensions-radio-warder-evolution_0.1.0-test13_all.ipk
SHA-256 `f112282cd121f2465bf16c10c2b78a2860d63fbbd4914f2d95f163b2a0353b3c`; 3045580 bytes.

Direct installation over old warderradio performs the renamed-package transition in one operation. The old updater still offers the immutable test11 bridge first; after restart its v2 updater offers test13. User receiver confirmation of outlines/spectrum/package migration remains pending.

The browser name, canonical package name, spectrum and automatic restart described below remain current; the prior test12 release evidence is retained for history.

---

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
