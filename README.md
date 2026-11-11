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
aktualizáciu. Streamripper sa inštaluje spolu s pluginom; uložené nahrávky možno prehrávať aj mazať.

Current release: **0.1.9.4**. The optional black Radio OLED screensaver
shows the live station, picon, song/artist, existing album art, native spectrum,
and localized clock in compact, gently moving panels. Choose **Settings →
Screensaver after**: Off / 10 / 20 / 30 / 60 seconds. The saved delay persists
across plugin restarts: when the last radio station autoplays, the saver starts
after the selected idle time without additional action. Any remote key wakes the
radio menu without stopping playback. The default remains Off. All 21 Radio
languages follow the active Enigma2 language.

Previous radio functionality includes a Settings action that switches between Stop
radio playback and Start radio playback. Starting restores the stopped radio
even after a different station is highlighted, without adding duplicate history.
Picon download progress, ordered log and final
summary inside the main Radio window. Favourite actions explicitly offer Add
or Remove according to the selected station; the catalogue action is labelled
Update radio catalogue in all 21 languages.
Settings and nested choices stay inside the main
Radio content panel, including country selection, custom-station text entry,
About and action confirmations. Green confirms; red returns or discards a draft.
Video cover artwork now sits on the infopanel title rail.
Picons are stored directly in the selected Radio folder.
The selected background and automatic 220 × 132 size choose the GitHub package;
no size or background subfolders are created on the receiver. Existing nested
Radio collections remain readable and are copied into the selected root during
the next picon download, preserving user images and the original files.
It upgrades both the previous stable 0.1.1 and the 0.1.2-testN picon candidates
through the plugin's existing verified update channels.
The preceding 0.1.0-test39 remains available as a receiver-test prerelease.

0.1.1 follows 0.1.0-test39 deliberately: the higher numeric version allows
opkg to upgrade rather than treat the stable package as an older build.
The plugin keeps favourites, history, cache, selected country, recordings and
all other Warder Radio state under /etc/enigma2/warder-radio.

Test2 fixes a receiver-reported bug where static artwork covered all live
widgets. Background, opaque dark panels and live controls now use explicit
z-order layers; the regression replay includes additional static widgets.

The upper-right header follows the approved PiconHub and Glass System Utility
layout: localized weekday and long date on two lines, large hour/minute digits
with smaller seconds, cyan dividing strokes and a translated Version caption.
The original Warder Radio skull/title graphic remains untouched. Header fields
scale with the native HD, Full HD, QHD and UHD layouts.

The approved layout uses the Warder graphic family, functions on the left,
stations in the centre and the player on the right. The header places the actual
package version after the clock. The approved transparent WARDER RADIO icon is
registered in the plugin browser.

## Universal country integration

The released plugin replaces the fixed picon country menu with all 219
catalogue countries and online package availability. Unpublished countries stay
visible; partial packages can be downloaded. Further country publication needs
only packages and an index update, with no new IPK. The receiver downloads only
220×132 in the chosen background. See [the architecture and publication order](docs/picon-country-availability.md).
The owner physically verified the blue confirmation and installation windows in 0.1.9.1-test1 package revision 2 and approved stable 0.1.9.2. The confirmation defaults to No; arrows choose Yes/No, OK confirms and EXIT cancels. The existing installation progress and safe update mechanism are unchanged. The YouTube no-result notice now uses the same Warder dialog design, with OK/EXIT and the original eight-second timeout; search and playback remain unchanged. Country paging uses the native visible page; OK alone toggles countries. Manual update results use a separate Warder dialog; OK/EXIT close it and green continues to the existing installation confirmation.

## Included

- Offline startup seed: 89 Slovak stations with original stream URLs
  and service references. From test34, the receiver loads one country at a time.
  A small versioned manifest lists every country; only selected/previously visited
  countries are cached. Explicit updates download changed visited packages only.
  Validation and atomic cache writes run off the GUI thread. Slovakia and Czechia
  remain first; the original-source view is loaded only when selected.
  Startup uses a cached country or the small bundled Slovak seed, with no network
  request or full legacy-cache migration before the window is usable. Install test34
  or newer once, then use MENU → Update catalogue for subsequent data updates.
  Genres, languages and other source metadata remain in the central database for
  future views; this release exposes the country list and station search.
- Native Enigma2/GStreamer playback, station and available ICY artist/title data.
- Yellow: station Search. Blue: current-song YouTube video in the receiver's
  standard MoviePlayer and active skin, with native progress/time/video details.
  Favourite is in MENU. DASH video plus separate audio is preferred when the
  Exteplayer3 executable and registered ServiceApp 5002 backend are available;
  otherwise combined video/audio or HLS uses the native backend. No image-wide
  player settings are changed and optional backends are not auto-installed.
- Persistent favourites, last 100 played stations, accent-insensitive search
  across the catalogue and custom HTTP/HTTPS stations.
- Picon lookup from the configured Radio collection, with a neutral Warder fallback.
- Main left menu → Picon downloads, directly below Radio stations: select multiple countries, a transparent,
  white or black background and an internal or currently mounted location.
  The centre and right panels become one wide numbered settings form.
  Country, background and folder lists appear inside this same panel. Each
  selection applies with Green → Confirm selection; Back discards pending changes.
  Folder choices include labelled
  internal storage, HDD, USB, SD, MMC, /picon and a custom directory. Missing
  external storage cannot silently write to receiver flash. Custom folders use
  a read-only directory browser inside the same panel: OK opens a directory,
  the `..` row opens its parent, and Green → Use folder confirms the displayed
  location. No path keyboard is opened. Repeated instructional text is removed.
  Radio collections use `picon/warderradio` beneath the selected storage root,
  for example `/media/hdd/picon/warderradio` or `/media/usb/picon/warderradio`.
  Selecting an existing `picon` or `warderradio` directory avoids duplicating
  that suffix. The plugin immediately reloads the confirmed location.
  Size is automatic (220×132). Available country packages are currently Slovakia,
  Czechia, Austria, Germany, Hungary and Poland. The scrollable progress window
  logs checks, downloads, verification and each saved station in order; red cancels.
  Green starts downloading from the form; LEFT returns to the main menu.
  Verified packages come from PiconHub's existing radio collections, filtered
  by the selected countries' station identities. The final summary distinguishes
  new, updated, current, preserved, missing and failed items. Missing station
  artwork retains the neutral fallback. Closing the log refreshes the picon library;
  red/EXIT in the form restores the preceding station view and selection without
  restarting the GUI or interrupting playback.
  The selected collection is the source inside Radio; other system picon folders
  are not searched when it is configured. A custom reference-named
  PNG in the selected Radio variant directory takes precedence over its managed
  image. Editing a managed image also protects it from later replacement.
  Previous Radio storage locations remain readable during the upgrade. The
  next download copies verified existing images and user overrides on the I/O
  worker, preserving the original files and avoiding an unchanged ZIP download.
- Mounted-disk recordings folder `/media/hdd/WarderRadio`; playback of recordings.
  The package depends on `streamripper`; opkg installs it from the receiver’s configured feeds.
  Blue/Delete in Recordings, or MENU → Delete, removes the selected recording after confirmation.
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
  channel. When the first stable package is published, the testing feed also
  temporarily advertises that same stable package to promote installed
  0.1.0-testN builds safely. The feed advances only after its public IPK
  bytes and SHA-256 have been verified.
- Native layouts at 1280×720, 1920×1080, 2560×1440 and 3840×2160; list heights
  always contain an exact number of complete rows.

The animated bars indicate playback activity. They are decorative and are not a
measured audio spectrum. Cover-art lookup is available from test17. Lyrics,
a sleep timer and recording schedules are not included.

## Install and use

Existing installations update through **Settings → Update** (or the left Update entry).
When a release is available, press green in the result window, then confirm the
installation. SHA-256, package identity and installed state are verified before
success and the GUI restart. No manual IPK download is needed.

Stable 0.1.8/0.1.9/0.1.9.1 and existing 0.1.9/0.1.9.1 test builds update
directly to 0.1.9.2 through the same verified update mechanism. This includes
0.1.9.1-test1 package revisions 1 and 2 and the published migration test2.
Both v2 channels offer the same stable 0.1.9.2 with their correct channel labels.
Its higher numeric version avoids opkg's same-version test/stable ordering
problem; no new migration package or downgrade exception is needed. See the
[0.1.9.2 update guide](docs/stable-update-0.1.9.2.md) and
[verified release record](docs/releases/radio-0.1.9.2.json).

The installed 0.1.8/test2 verifier may report "Warder Radio package is not
completely installed" after a successful first update, because it only accepts
`install ok installed` and rejects opkg's valid `install user installed` state.
If that exact legacy message appears, restart the GUI once. The new updater
accepts both complete states, checks the exact package/runtime version, and
retains the automatic successful-update restart. Never retry a package install
blindly after a different error; that error needs its own diagnosis.

For a first installation only, copy the IPK to `/tmp`, then run:

```sh
opkg install /tmp/enigma2-plugin-extensions-radio-warder-evolution_0.1.9.2_all.ipk
```

Restart the GUI manually, then open **Radio Warder Evolution** from Plugins or Extensions.
No stream starts during installation or plugin discovery. On opening the plugin,
the last played radio station resumes automatically and is selected in its list.
On first use, choose a station and press OK or green. Resume uses the newest
catalogue URL for the remembered identity where available, with the saved entry
as fallback. It makes one attempt and leaves the interface usable on failure.
The country selector is the first item of the left function menu, above Radio stations.
It is raised slightly and separated visually from the radio-list menu item without
using eight complete compact menu rows. The navigation hint beneath the logo
follows the receiver's system language across all 21 supported locales.
Its current country is shown in Warder cyan, slightly larger and higher in the left panel. There are eight fully visible station
rows in the centre at every supported resolution, without shrinking picons.
UP/DOWN select stations normally. RIGHT pages the station list down; LEFT
pages up, and only when the first station is selected does LEFT move to the
left function menu. RIGHT from the menu returns to the previous station and
scroll position. Press 0 from any station to focus Choose country in the left
menu; OK opens its country choices. UP from the first station no longer changes
panels. UP/DOWN inside the left menu move among its eight function entries,
wrapping normally. MENU → Choose country remains available as well.
Selecting a country preserves playback and saves the choice. Cancel keeps the
previous selection. The left function-menu selection identifies the active section, including
favourites, history and recordings. CH+/CH− change pages. Yellow searches all
stations; blue opens the current song’s YouTube video. Favourites are available in MENU. Update is the last left-menu entry, below Settings;
activate it or press INFO to check/install plugin updates manually. After a verified
successful installation, an information message appears for three seconds and
the GUI restarts automatically. Failed updates do not restart the GUI. The first MENU/Settings entry is Choose country and opens the same selector.
MENU also updates the catalogue, adds a
station, controls recording and opens About. STOP stops radio playback and
returns to the previous service. EXIT/red closes the plugin and restores the
previous service, unless another application has already changed navigation.

The REC key starts/stops a streamripper recording of the playing
station. Closing the plugin stops its recorder. At least 100 MB free on a mounted
`/media/hdd` is required. Recordings opens saved audio files for playback. Blue/Delete
or MENU → Delete asks before removing the selected file. Cancel leaves it untouched.
Stop recording before deleting files. Deleting the file currently playing also stops
its playback; listening to another radio station continues. Only listed, unchanged
audio files inside the configured recording folder can be removed. Symlinks and
other files are rejected. If the image feed does not provide streamripper, opkg
reports the missing dependency and installation cannot complete.

YouTube videos reuse the current radio song’s downloaded cover/artist image.
A small transparent image appears on the left above the native information bar,
scales with the GUI resolution and follows the bar’s show/hide controls. A cover
that finishes loading during the clip is added then. No extra artwork lookup or
video-start delay is introduced; a missing image leaves the player clear. Closing
the player removes the image. The image’s MoviePlayer skin and controls remain.

Opening the window does not wait for validation of the full station catalogue.
The catalogue loads on the existing I/O worker after the initial layout; the
window shows a translated loading indicator meanwhile. Reopening reuses up to
two validated file snapshots when file identity, size and timestamps match.
Changed catalogues are revalidated, and each window owns its own row copies.
Last-station playback and update checks follow catalogue display. User input or
external channel changes during loading cancel automatic last-station playback.
Idle artwork/video workers are created only when their first job is submitted.

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
the station list shows eight complete rows. A 520-pixel square cover at Full HD
fits above all track details. The spectrum is in the left panel. Action/error feedback is retained
inside the left panel instead of using a separate full-width row.

The country-selector menu row uses the normal Warder selection highlight;
its country name remains cyan. Country choices still open only with OK.

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
