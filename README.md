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
**0.1.0-test7**. It is not a production release and is not added to existing stable feeds.

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
  installed opkg status are verified. GUI restart is offered after success.
  Test builds use the testing channel; stable builds use the separate stable
  channel. The feed advances only after the public IPK download is verified.
- Native layouts at 1280×720, 1920×1080, 2560×1440 and 3840×2160; list heights
  always contain an exact number of complete rows.

The animated bars indicate playback activity. They are decorative and are not a
measured audio spectrum. This first candidate does not include cover-art lookup,
lyrics, a sleep timer or recording schedules.

## Install and use

Copy the IPK to `/tmp`, then run:

```sh
opkg install /tmp/enigma2-plugin-extensions-warderradio_0.1.0-test7_all.ipk
```

Restart the GUI manually, then open **Warder Radio** from Plugins or Extensions.
No stream starts during installation or plugin discovery. On opening the plugin,
the last played radio station resumes automatically and is selected in its list.
On first use, choose a station and press OK or green. Resume uses the newest
catalogue URL for the remembered identity where available, with the saved entry
as fallback. It makes one attempt and leaves the interface usable on failure. Left/right switch between the function and station panels;
up/down move within a panel. From the first station, UP focuses the country
selector above the station list; OK opens the selection directly. DOWN returns
to the station list. The native country button also supports its click action.
The centre header reads Select country – Slovakia ▾ (translated for the receiver
language and current country). Select country and the separator are white; the country and down arrow are
cyan blue, using the native Enigma2 inline text colours. The permanent down
arrow marks the selectable value; remote focus adds a leading pointer. The former Country
heading on the left is blank; Now playing stays on the right.
Selecting a country preserves playback and saves the choice. Cancel keeps the
previous selection. The smaller section label still identifies favourites,
history, recordings and search results. CH+/CH− change pages. Yellow toggles a favourite;
blue searches all stations. The fifth footer button is INFO · Update; press
INFO or activate the button to check/install plugin updates manually. The first MENU/Settings entry is Choose country and opens the same selector.
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
components. It contains no HDF Radio binaries or bytecode. Tests replay real
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
