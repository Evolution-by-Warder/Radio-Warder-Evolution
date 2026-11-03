# Warder Radio — World of Radio Stations

Independent native Enigma2 internet radio plugin.

Official source: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution

Releases and IPKs: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases

 Warder Radio brings internet radio to Enigma2 receivers in the Warder graphic
style: functions on the left, stations in the centre and live playback on the
right. It combines the owned PiconHub catalogue with persistent favourites,
listening history, native picons, recording support and verified updates.

**Slovensky:** Samostatný rádiový plugin pre OpenATV a OpenPLi s našou grafikou,
rýchlym výberom krajiny, obnovením poslednej stanice, obľúbenými, históriou a
piconami. Obsahuje všetkých 21 jazykov našich pluginov a automatickú aj ručnú
aktualizáciu. Nahrávanie využíva voliteľný streamripper.

Current receiver-test candidate:
**0.1.0-test26**. It is not a production release and is not added to existing stable feeds.

Test2 fixes a receiver-reported bug where static artwork covered all live
widgets. Background, opaque dark panels and live controls now use explicit
z-order layers; the regression replay includes additional static widgets.

The approved layout uses the Warder graphic family, functions on the left,
stations in the centre and the player on the right. The header places the actual
package version after the clock. The approved transparent WARDER RADIO icon is
registered in the plugin browser.

## Included

- Bundled PiconHub/Warder catalogue: 5,444 stations in 203 groups, with original
  stream URLs and service references. Updates are explicit, from the same Git
  bouquet; the bundled/cached list remains usable without the catalogue server.
- Native Enigma2/GStreamer playback, station and available ICY artist/title data.
- Yellow: station Search. Blue: current-song YouTube video in the receiver's
  standard MoviePlayer and active skin, with native progress/time/video details.
  Favourite is in MENU. DASH video plus separate audio is preferred when the
  Exteplayer3 executable and registered ServiceApp 5002 backend are available;
  otherwise combined video/audio or HLS uses the native backend. No image-wide
  player settings are changed and optional backends are not auto-installed.
- Persistent favourites, last 100 played stations, accent-insensitive search
  across the catalogue and custom HTTP/HTTPS stations.
- Native/PiconHub picon lookup, with a neutral Warder Radio fallback logo.
- Mounted-disk recordings folder `/media/hdd/WarderRadio`; playback of recordings.
  Optional recording uses the separately installed `streamripper` executable.
  Its stream/codec/TLS support depends on the receiver's streamripper build.
- All 21 languages used across FullHDGlass, GSU and PiconHub: Albanian, Czech,
  German, Greek, English, Spanish, Estonian, Persian, French, Hungarian, Italian,
  Lithuanian, Dutch, Polish, Portuguese, Romanian, Russian, Slovak, Turkish,
  Ukrainian and Chinese. Language follows the receiver; Albanian supports both
  `al` and `sq` codes. The approved subtitle stays in English.
- Automatic update check on opening, plus MENU → Check for updates. Installation
  is offered with confirmation, then size, SHA-256, package identity/version and
  installed opkg status are verified. After success an information message lasts three seconds and GUI restarts automatically.
  Test builds use the testing channel; stable builds use the separate stable
  channel. The feed advances only after the public IPK download is verified.
- Native layouts at 1280×720, 1920×1080, 2560×1440 and 3840×2160; list heights
  always contain an exact number of complete rows.

The animated bars indicate playback activity. They are decorative and are not a
measured audio spectrum. Cover-art lookup is available from test17. Lyrics,
a sleep timer and recording schedules are not included.

## Install and use

Copy the IPK to `/tmp`, then run:

```sh
opkg install /tmp/enigma2-plugin-extensions-radio-warder-evolution_0.1.0-test26_all.ipk
```

Restart the GUI manually, then open **Radio Warder Evolution** from Plugins or Extensions.
No stream starts during installation or plugin discovery. On opening the plugin,
the last played radio station resumes automatically and is selected in its list.
On first use, choose a station and press OK or green. Resume uses the newest
catalogue URL for the remembered identity where available, with the saved entry
as fallback. It makes one attempt and leaves the interface usable on failure. LEFT
opens the function panel; RIGHT from that panel returns to stations. Up/down
move within a panel. From any station, RIGHT focuses the cyan country value. UP from the first
station row does the same. Focus adds › country ‹ markers only around that
value, with a blue field background and the white caption unchanged. Press OK to open country choices;
DOWN or RIGHT returns to the same station without opening a dialog. In the left menu, UP/DOWN
move only between function entries, wrapping from first to last and back. Cancel returns
to the exact same station and scroll position. The native country button also supports its click action.
The centre header reads Select country – Slovakia ▾ (translated for the receiver
language and current country). Select country and the separator are white; the separate country value and down
arrow are cyan blue. The permanent down
arrow marks the selectable value; remote focus adds a pointer beside only the cyan country name. Only the focused country value gets the blue selection background; the white
caption stays on the panel background. The left menu is separate.
Selecting a country preserves playback and saves the choice. Cancel keeps the
previous selection. The smaller section label still identifies favourites,
history, recordings and search results. CH+/CH− change pages. Yellow toggles a favourite;
blue searches all stations. Update is the last left-menu entry, below Settings;
activate it or press INFO to check/install plugin updates manually. After a verified
successful installation, an information message appears for three seconds and
the GUI restarts automatically. Failed updates do not restart the GUI. The first MENU/Settings entry is Choose country and opens the same selector.
MENU also updates the catalogue, adds a
station, controls recording and opens About. STOP stops radio playback and
returns to the previous service. EXIT/red closes the plugin and restores the
previous service, unless another application has already changed navigation.

The REC key starts/stops an optional streamripper recording of the playing
station. Closing the plugin stops its recorder. At least 100 MB free on a mounted
`/media/hdd` is required. Recordings are not deleted by the plugin.

Settings are stored atomically in `/etc/enigma2/warder-radio/state.json` and are
preserved by upgrades/uninstall. Installation writes only Warder Radio's own
plugin and documentation directories; it does not patch the skin, firmware,
other plugins, global keymaps or stable update feeds.

## Compatibility and verification

Runtime is architecture-independent Python 3.9+ and uses native Enigma2
components. Tests replay real
OpenPLi release-9.2 and OpenATV Python classes with the C++ GUI/OS boundary stubbed.
See `tools/native-fixtures.json` for exact source commits and file hashes,
including the previously reviewed OpenATV 8.1 base and 8.0-next.

These tests check screen binding/lifecycle, full rows at four resolutions,
metadata, favourites, history, private remote mappings, timer cleanup and return
to TV. Unit tests cover catalogue parsing, persistence, update failure,
thread dispatch, navigation ownership and recording process handling.
**Receiver audio, GPU/GLES painting and physical remote behaviour still need a
real receiver test.** The catalogue does not assert every stream is online.

Build locally with `python3 tools/build_ipk.py`. Run unit tests with
`PYTHONPATH=src python3 -m unittest discover -s tests -v`. For the native replay,
run `python3 tools/test_native.py --upstream /path/to/enigma2/lib/python -v`.

## Provenance

Catalogue: `Evolution-by-Warder/PiconHub-Warder-Evolution`, source and commit in
`src/WarderRadio/catalogue-source.json`. Original Warder Radio background and
logo were generated for this project using the owner's supplied brand references.
The full logo master is retained in `artwork/warder-radio-logo.png`; the plugin
uses `plugin.png`. No existing unrelated logos were changed.

License: GPL-2.0-or-later. Copyright 2026 Warder.

The plugin and extensions menus display Radio Warder Evolution.

The playback visual reuses the approved FullHDGlass multicolour segmented spectrum
with peak markers. Prepared transparent frames play at up to 10 frames per second,
with a shared bounded cache. It pauses while hidden or idle. This is a decorative
playback animation, not a measured audio spectrum.

The installed package is named radio-warder-evolution. Its IPK replaces and
conflicts with the former warderradio package, taking over the same owned files
and preserving /etc/enigma2/warder-radio. It can be installed directly over an
older build. Older in-plugin updaters first offer the test11 compatibility bridge
under the original package name; after the GUI restart it uses the v2 feed and
offers the renamed package. This avoids bypassing package identity checks.

Track metadata primarily reads ICY StreamTitle directly from internet-radio
streams, using the bounded reader from FullHDGlass radio mode. Native Enigma2
tags are the fallback when ICY is absent, unavailable or still loading. ICY reads run
on one background worker, with a 15-second refresh interval; station changes
and closing discard stale results. Streams without song metadata still show
No track information. No extra audio playback is started for the metadata probe.

The player panel now places a square current-song cover above the artist/title
and a compact station name. iTunes search uses the same strict full
recording identity as FullHDGlass, with artwork-specific handling of abbreviated
ICY credits and descriptive song subtitles. An initial global iTunes music
query avoids regional retries for a usable first result. TheAudioDB artist thumbs are a fallback when
the entire artist credit matches. An early iTunes exact-artist fallback is
labelled as artist artwork in the receiver's language. Default Original Mix
suffixes may be omitted by the catalogue. A unique live recording may supply
its album cover when the album corroborates the omitted performance suffix.
Provider attribution appears beneath images.
Unavailable/unknown artwork shows the neutral Warder graphic. Candidate checks
reject unrelated artists and conflicting versions. Lookups run in a separate bounded worker and cached JPEGs stay in
a bounded RAM cache. Country navigation and the four colour actions are retained.

The separate Playing status row is removed. All three panels extend downward;
the station list shows seven complete rows. A 520-pixel square cover at Full HD
fits above all track details. The spectrum is in the left panel. Action/error feedback is retained
inside the left panel instead of using a separate full-width row.

When focused, only the country value has the same blue background as a selected
menu/station row; the white Select country caption stays on the panel background.
The value field is positioned using the rendered caption width for each locale.
Country choices still open only with OK.

The function menu starts higher in the left panel. Its lower area contains the
multicolour spectrum, leaving the right panel for the larger square cover and
track information.

Artwork provider details: [iTunes Search API](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/index.html)
and [TheAudioDB](https://www.theaudiodb.com/docs_json). Provider artwork remains
the property of its respective owners; it is fetched on demand, not bundled.

After confirming an update, a modal progress window opens before I/O starts.
Download progress uses actual bytes and percentage. Package verification, opkg
installation and installed-state verification show their current phase with a
visible activity indicator, without inventing an installation percentage. A
verified success changes the same window to the three-second restart notice;
a failure shows its reason and allows OK/EXIT to return without restarting.
The new progress UI applies to updates initiated by test18 and later.

The three main panels and the update window share PiconHub's subtly translucent
navy fill. Text labels have transparent backgrounds so they do not create opaque
patches over that fill. Text, artwork, cyan borders and selected-row highlights
retain their normal contrast. Layout, controls and update behaviour are retained.
