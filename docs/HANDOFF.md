# Radio Warder Evolution — test21 omitted version and artist artwork

Receiver screenshots reproduced three additional misses in test20:
BCC Worship / Si pri mne blízko; Jackers Revenge / Comin Out (Once Again)
(Original Mix); Dianah Kay / ILLUMIN8. Independent live public API queries found:
- The BCC song is the sole matching result, labelled Live Chapel, with the same
  suffix in its album. A unique exact-artist/title-base album family can now
  provide that cover when ICY omitted the live suffix.
- The Jackers Revenge catalogue title omits Original Mix. Only terminal default
  Original Mix/Original Version labels are normalized; meaningful title
  parentheses are preserved and explicit conflicting remixes remain rejected.
- The Dianah Kay song is unavailable in the queried catalogues. An exact-artist
  query returns jazvy. Early artist fallback now provides that image with the
  translated Artist artwork credit rather than claiming it is an ILLUMIN8 cover.

No song-specific hardcoded matching aliases were added. Shared lyrics/recording
identity and ICY display are unchanged. Positive artist-fallback JPEGs use the
same bounded RAM cache and stale-result guards. One new key is translated in
all 21 catalogues (72 keys each); native replay verifies the Slovak fallback
credit and cleanup on stop/late callbacks.

Local verification: 54 unit cases, 22 native cases on each of three pinned
OpenPLi/OpenATV revisions (120 executions), and package/Python 3.9/offline scripts.
Publication additionally requires live two-request cover downloads for CHILL77,
BCC Worship and Jackers Revenge, and a three-request artist fallback for Dianah
Kay. Receiver latency and visual confirmation remain pending. Publication
results will be recorded after public-byte and testing-feed verification.

---

# Radio Warder Evolution — test20 short-credit artwork lookup

Fix the receiver-reported CHILL77 / PAPAOUTAI miss. A live public iTunes query
returns mikeeysmind, Chill77 & Unjaps / Papaoutai (Afro Soul), while test19's
complete recording identity rejects it. Artwork-specific ranking now accepts
whole credited names within abbreviated ICY tags and omitted descriptive title
subtitles, retaining exact matches first and rejecting conflicting remix/live/
acoustic/instrumental results. Shared song/lyrics identity is unchanged.

The first request uses the default iTunes music catalogue, limit 20, HTTPS;
regional and title searches remain fallbacks. An accepted first result requires
one search plus one image request. Optional trace callbacks expose requested/
final URLs, timings, candidate rank and the selected image without normal-playback
logging. Actual receiver latency and visual confirmation remain pending.

Local verification: 50 unit cases and 22 native replay cases on each of three
pinned OpenPLi/OpenATV revisions (116 executions), plus IPK/Python 3.9 grammar,
owned paths and offline install-script checks. The publication workflow now also
requires a real CHILL77 cover download in two requests before publishing.
Source: 145d3e24d5370134b1ac8bd44089bf2e0642c327.\nCI: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41652995788 — success.\nAll build, native tests, live lookup, publication and public-feed steps passed.\nThe real cover downloaded in two requests: catalogue 0.331s, image 0.038s,\n59,310-byte JPEG. These are hosted-runner timings, not a receiver guarantee.\nPublic IPK and v2 feed agree: 3,060,018 bytes, SHA-256\n`a10571a830514bc36bee77f6bac6fa1b2d9aae8a897690e118466cff663798ad`.\nURL: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.0-test20/enigma2-plugin-extensions-radio-warder-evolution_0.1.0-test20_all.ipk\nTesting feed now offers test20. Stable feeds and the immutable test11 migration\nbridge are retained.

FullHDGlass Radio Mode follow-up is queued in both NEXT-RELEASE.md and
PROJECT-CONTINUITY.md, commit 3d13f41e2d497dccbca78949e73d22783ed2cca9.
This note changes no skin runtime or feed. The public laut.fm API may be useful
as a supplementary station catalogue; it is not integrated by this release.

---

# Radio Warder Evolution — test19 translucent surfaces

User requested partially transparent window/panel backgrounds in the same style
as the other Warder plugins. Applied the exact PiconHub panel navy #18091b30
(Enigma2 alpha 0x18) to all three radio panels and the update progress window,
through the shared PANEL_BACKGROUND constant. Popup text fields are now fully
transparent over that fill rather than repainting opaque rectangles. Text,
images, cyan borders, list highlights and the focused-country background retain
their existing opacity/contrast. Layout, navigation, artwork, metadata and the
verified-update/restart flow are unchanged. The full-screen brand artwork is
unchanged; main-panel translucency reveals that existing background, while the
popup blends with its underlying window. Default image-owned native dialogs
and other plugins were not modified.

Lookup/matching uses our independent Python implementation with shared
FullHDGlass recording identity/curated aliases. Current title
is primarily ICY with native Enigma2 fallback. External artwork catalogues are
iTunes (song cover) and TheAudioDB (artist thumb); the catalogues themselves are
external, not an invented owned music database.

Source: `5fbd14476c0d49720d07bb6e66837177ad678ee9`.
CI: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41646251477 — success.
46 unit cases plus 22 native cases on each of three pinned OpenPLi/OpenATV
revisions: 112 executions. Existing render-order/geometry assertions were updated
for the requested translucency and transparent popup labels. IPK/Python 3.9 and
script checks passed. CI downloaded/verified public IPKs before feed publication;
connector public asset digest/size match the v2 feed. Receiver alpha composition
and subjective appearance remain pending user review. Locale count remains 21,
71 keys each. Stable/other-product feeds and immutable test11 bridge are retained.

Latest IPK: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.0-test19/enigma2-plugin-extensions-radio-warder-evolution_0.1.0-test19_all.ipk
SHA-256 `19da835d7d7c727d96f0b8c2daac6300ad892dc6c2cfcf90712117ac2c8e4a66`; 3058762 bytes.

---

Prior release records follow; opaque panel/popup fills described below are
superseded by test19.

# Radio Warder Evolution — test18 update-progress window

The requested installer flow is complete: existing confirmation, then a modal
progress window before I/O, real download bytes/percentage, live package/opkg/
installed-state phases, then the three-second restart notice in that window.
Only its successful close callback opens the standard GUI restart. Failures
show the reason and restore control with no restart. OK/EXIT cannot dismiss an
active install; a failed dialog can be closed normally. Unknown installation
percentages are not fabricated: those phases hide the byte bar and show an
animated activity indicator. Worker reports use a single-slot locked mailbox;
all widget updates occur through the GUI timer. Downloads report in 32 KiB chunks.

Four new translated phase/wait strings are present in all 21 languages: 71 keys
per locale. ProgressBar/VariableValue are pinned to the exact same three native
fixture revisions as the other Enigma2 classes. The popup supports both eTimer
signal APIs and four display resolutions. Native replay caught/fixed the Screen
shown-property collision and pixel-rounded border overflow before publication.
Main layout/artwork were not redesigned; the user wants graphics work after this.

Source: `29a65f544b435d201f4c064ae66aa9036daca3ce`.
CI: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41639642305 — success.
46 unit cases plus 22 native cases on each of three pinned OpenPLi/OpenATV
revisions: 112 executions. Coverage includes modal-before-I/O ordering, actual
byte counts, phase ordering around real IPK validation and mocked opkg, failed
installed-state verification (no complete event), mailbox coalescing, busy input,
queue rejection, both timer APIs, error return, modal close-before-restart,
duplicate/late callbacks, cleanup and HD/FHD/WQHD/UHD geometry. Package/Python 3.9
and install-script checks pass. Physical receiver confirmation is pending.

The old updater already running in test17 cannot display newly installed code
before its own restart: the new window is used by updates initiated from test18
or later. A manual test18 install plus GUI restart is also supported. Existing
immutable old-ID bridge and separate stable feeds remain unchanged.

Latest IPK: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.0-test18/enigma2-plugin-extensions-radio-warder-evolution_0.1.0-test18_all.ipk
SHA-256 `797e8dcddcddb8919f22e9ef5c358ad37bded822889e3793cb4de64b2c259de6`; 3058538 bytes. CI downloaded/verified public IPKs before
advancing the v2 test feed; connector release size/digest independently match.
More implementation/transition notes: docs/UPDATE-PROGRESS.md.

---

Prior release records follow.

# Radio Warder Evolution — test17 artwork and layout

Latest user requests are implemented together:
- Replace the upper Now playing, station logo and large station name with current-song artwork. The final right panel uses a 520x520 cover at Full HD, with provider credit, a compact station name, artist, title and country below it.
- Remove the separate Playing row and extend all three panels from 730 to 790 px, ending at y=994 above footer buttons. The station list contains seven complete 94px rows. Other action/error feedback is retained inside the left panel.
- Raise the function list to y=230. Put the multicolour spectrum below it in the left panel, freeing the right for artwork/text.
- Focused country value uses list-selection blue (#004461) and cyan text; the white Select country caption stays on the regular panel background. Caption/value are separate native components positioned using rendered caption width, bounded to the centre panel. Arrows focus only, OK opens choices. Left-menu wrapping from test15 remains.

Artwork reuses FullHDGlass's complete song identity, curated aliases and regional iTunes query order. TheAudioDB's public documented artist thumb endpoint is an exact-artist-credit fallback. Unavailable or unknown artwork uses the approved neutral Warder graphic. Provider name appears beneath loaded images. One separate worker and a generated RAM cache (64 JPEGs/16 MiB) keep artwork I/O away from playback/ICY/update workers. Reads have an 18-second common deadline, timeout and size limits, trusted image hosts, exact matching and bounded retries. Native ePicLoad supports both signal APIs; request generations, callback tokens and close guards reject stale results. Optional lookup/decoder errors fall back without affecting radio. Details and primary documentation links are in docs/ARTWORK.md.

Source: `0579084ebd87bf17735b2da17e6f461c906e8981`.
CI: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41635118402 — success.
43 unit cases plus 20 native cases on each of three pinned OpenPLi/OpenATV revisions: 103 executions. These cover full/partial identity and versions, artist fallback, caches and response bounds, unavailable providers, both decoder signals, failed decoders, late callbacks, old-song worker results, selected-country background, expanded geometry, seven whole rows, no separate Playing label and all previous behaviour. Package/Python 3.9/install-script verification passed. CI downloaded and verified the public IPKs before feed publication; connector public asset digest/size matches the v2 feed. Archived test1 z-order fixture alone produces missing section/countrycaption warnings; current skin includes both.

Live third-party lookup availability, actual receiver JPEG decode/painting, font metrics and the new layout/focus visuals still require user testing. No success on those physical checks is claimed. Previous receiver confirmation of test14 name and ICY text remains valid. All 21 locale catalogues and stable feeds are unchanged. The immutable old-ID test11 bridge still leads to the latest v2 release.

Latest IPK: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.0-test17/enigma2-plugin-extensions-radio-warder-evolution_0.1.0-test17_all.ipk
SHA-256 `d7b2e54ad7d8f1a509dbe88ad2c6ecf39ebf5ea4e4c096cafc793d091d52cb36`; 3055012 bytes.

---

Prior release records follow; old right-panel spectrum, separate Playing row and marker-only country focus are superseded by test17.

# Radio Warder Evolution — test16 country focus

Latest user preference supersedes test9–15's immediate country dialog. UP from the first centre station and RIGHT from any station now only focus the cyan country value. Its cyan pointers read › country ‹; the white Select country caption does not change. No country dialog appears until OK. DOWN or RIGHT returns from the control to the exact selected station. Cancel in the choice dialog returns to the focused country control; selecting a country returns to stations. Left-menu UP/DOWN retain normal within-menu wrapping. Playback is unchanged.

Source: `160c776509d995f2fbf055fc494c3543ed1fe991`.
CI: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41631904554 — success.
36 unit cases plus 17 native cases on each of three pinned OpenPLi/OpenATV revisions: 87 executions, plus IPK validation. Updated regression checks no dialog on arrows, cyan value-only markers/white caption, first/middle/last station positions, OK-only open, cancel/return, saved country and uninterrupted playback. Left menu regression remains passing. CI downloaded/verified public IPKs and published v2 feed; connector release digest/size match that feed. Receiver confirmation of this latest focus behaviour remains pending.

Latest IPK: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.0-test16/enigma2-plugin-extensions-radio-warder-evolution_0.1.0-test16_all.ipk
SHA-256 `dcf4de992bb7b1a8cb586a4f4d0c2c7e720fd63fdbe8dbd4fc46fdfa0b4908c1`; 3047966 bytes.

---

Prior release records follow; the immediate-open arrow behaviour described below is superseded by test16.

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
