# 0.1.2-test2 (embedded picon settings and spectrum recovery)

- Place Picons immediately below Radio stations in the main left menu.
  Opening it replaces the centre and right content panels with one wide,
  numbered country/colour/location form in the existing Radio window.
- Green starts the existing line-by-line download log. LEFT returns to the
  main menu; red/EXIT restores the preceding station view and selection.
  Playback continues, and delayed artwork cannot cover the settings form.
- Fit all eight main menu rows above the status and spectrum areas at HD,
  Full HD, QHD and UHD. Keep image size automatic.
- Resume the decorative equalizer after returning to the main screen and
  use the clock as a watchdog for a paused animation timer. Retry transient
  frame-load failures at most three times; returning or starting a station
  permits recovery without repeated work while hidden or closed.
- Keep all 48 approved equalizer frames unchanged. Receiver verification of
  the reported missing equalizer remains necessary.

# 0.1.2-test1 (picon downloader candidate)

- MENU → Download / update picons selects one or more available countries,
  transparent/white/black colour and internal or mounted storage. The plugin
  selects 220×132 images automatically; no resolution choice is shown.
- A separate window shows an ordered, scrollable log for country checks,
  downloads, package verification and individual station saves, plus real
  download progress, cancellation and a final summary.
- Read verified PiconHub radio packages for Slovakia, Czechia, Austria,
  Germany, Hungary and Poland. Filter every package through the selected
  country's catalogue identities; shared SK/CZ packages download once.
- Verify archive and PNG hashes, dimensions and inventory before publishing
  images. Publish immutable PNGs and their index atomically, resume interrupted
  installs, skip unchanged packages and retain custom picons. Reopen the list
  with its current selection after setup closes, without a GUI restart.
- Preserve playback, favourites, catalogue state and native picon lookup.
  All new controls and log messages use the existing 21 interface languages.
- This candidate does not advance either update feed. Physical receiver
  painting, remote control and storage behaviour need a receiver test.

# 0.1.1 (first stable release, OpenATV / OpenPLi)

- Promote the tested Warder Radio 0.1.0-test39 functionality to a stable version
  with a safe numeric upgrade from all 0.1.0-testN packages through opkg.
- Retain Warder branding and three panels, PiconHub integration, the eight
  complete station rows, translated controls, local calendar and GSU/PiconHub
  style header, current-track artwork, YouTube player, streamripper recording,
  favourites and country catalogue caches.
- Publish a dedicated stable manifest with a public, verified IPK (SHA-256,
  package identity and size). Advertise the same verified stable release in
  the testing feed so installed test builds can upgrade directly.
- Preserve the pre-test11 migration bridge and legacy feed without modifying
  any global Enigma2 skin, keymap or external plugins.
- Availability of individual streams and physical GPU/audio behaviour still
  depends on receiver, Enigma2 image and service provider.

# 0.1.0-test39 (receiver-test update)

- Match the PiconHub/GSU header geometry exactly: two-line weekday/date, prominent HH:MM with smaller :SS, two narrow cyan separators, localized Version label above the package version.
- Use the receiver's local time and interface language (all 21 Warder locales) with bundled weekday/month names; no system-locale mutation and no additional runtime dependency.
- Preserve the approved Warder Radio skull/logo, the left menu, eight station rows, equalizer, cover art, video and native controls.
- Repair the test38 native regression's incorrect zero-position expectation (Enigma2 integer scaling clamps positions to 1).
- Validate header fields, geometry, translation and local time before a testing-feed release. No stable feed changes.

# 0.1.0-test38 (receiver-test update)

- Localize the top station-navigation hint to the Enigma2 system language in all 21 supported Warder locales.
- Raise the country selector by another 14 Full HD pixels (246 to 232); lift its text within the first row and lower the following menu item text to create a clear visual gap before Radio stations.
- Preserve all seven left-menu entries, eight complete station rows, original Warder spectrum, YouTube status and playback controls.
- Extend i18n and native Enigma2 navigation/layout regression tests.

# 0.1.0-test37 (receiver-test update)

- Raise the left-hand country selector by 32 Full HD pixels while keeping the other function entries and the spectrum within the Warder panels.
- Increase only the country selector typography from 20 to 24 (Full HD base) while keeping its label white and selected country cyan.
- Collapse the unused navtitle placeholder to prevent overlap; keep all seven menu rows, all eight station rows and remote-control behaviour unchanged.
- Move the top navigation-help line from the right edge to left alignment beneath the Warder Radio logo, keeping its current typography and colours.
- Add regression checks for left-menu positioning, clearance, help-text alignment and font size on supported resolutions.

# 0.1.0-test36 (receiver-test candidate; PR artifact only)

- Relocate the country selector from the centre header to the first left-menu entry, with the country value in Warder cyan.
- 0 focuses the first left-menu entry; OK opens country choices. The UP key remains ordinary station navigation.
- LEFT pages the station list upward, reaching the left menu only when the first station is selected. RIGHT continues paging downward and returns from the left menu to the same station.
- Show eight complete 94px station rows in the centre rather than seven without shrinking picons. Keep all seven function rows clear of the left header, status row and spectrum.
- Add layout and remote-control regression tests, plus read-only OpenPLi/OpenATV CI verification and build artifacts. The stable feed and existing released IPKs are unchanged.

# 0.1.0-test35

- RIGHT in a station list advances by a native page rather than moving focus to the country field. Held RIGHT repeats page jumps.
- 0 focuses the existing country field from any selected station; OK opens its country choices. UP from the first station, the heading button and MENU → Choose country remain available.
- Keep LEFT for the function menu and RIGHT there for returning to stations. Returning from the country field preserves the station/scroll position and playback.
- Update the station and country-focus hints across all 21 languages.

# 0.1.0-test34

- Load and cache the selected country from immutable versioned packages. Updates fetch the small manifest and only changed, previously visited country packages.
- Prepare downloads, validation and atomic cache writes on a dedicated I/O worker; the GUI activates a prepared country without revalidating or serializing the full world catalogue.
- Open from a cached country or the small bundled Slovak list. Existing favourites, history, custom stations and their service references remain usable; the old whole-world cache is not parsed on startup.
- Keep all countries visible, with Slovakia/Czechia first. Load the original-source list only on selection. Whole-world search is an explicit background operation and shows up to 200 matches; refine the query for more specific results.
- Show country/progress messages, supersede older selections and discard results after close. Country changes and catalogue updates do not stop radio playback.
- Keep the existing full catalogue endpoint available for older plugin versions. No package update is required for subsequent station-data changes.

# 0.1.0-test33

- Load the complete centrally compiled radio catalogue through compressed JSON.
- Support up to 100,000 stations without the previous 20,000-row truncation.
- Bound compressed downloads and decoded/cache sizes; reject invalid or incomplete updates while retaining the usable cache.
- Preserve the existing offline seed, worker startup, cached reopening, station references and saved favourites.
- Switch a removed provider group to the matching station's country after catalogue refresh.
- Keep the legacy catalogue address available to older plugin versions.

# 0.1.0-test32

- Enlarge the YouTube artwork by another 50%, from 240 to 360 px at Full HD.
- Keep the same 80 px left alignment and 12 px gap above the native information bar.
- Retain proportional scaling, aspect ratio, visibility and cleanup.

# 0.1.0-test31

- Enlarge the YouTube song artwork from 180 to 240 px at Full HD.
- Shift its left offset from 40 to 80 px while retaining the gap above the native information bar.
- Preserve proportional scaling, aspect ratio and native show/hide behaviour.

# 0.1.0-test30

- Show the radio song’s downloaded cover or artist image beside the native YouTube information bar.
- Follow the native bar’s visibility and accept a cover that arrives during the clip.
- Retain native controls and video quality; no additional artwork search before playback.
- Hide absent/failed images and clean up the cover window and decoder on return to radio.

# 0.1.0-test29

- Show the radio window before loading and validating the station catalogue.
- Reuse bounded validated snapshots on reopening; changed catalogue files are revalidated.
- Defer automatic last-station playback and update checks until the catalogue is displayed.
- Preserve user input and external channel changes during startup; ignore late callbacks after closing.
- Create idle I/O workers only when needed.

# 0.1.0-test28

- Install streamripper automatically as a required package dependency through the receiver’s configured feeds.
- Delete saved audio from Recordings with blue/Delete or MENU → Delete, after confirmation.
- Block deletion while recording; reject changed files, symlinks and files outside the recording folder.
- Stop playback when its selected audio file is deleted; retain unrelated radio playback.
- Translate the new controls and messages into all 21 supported languages.

# 0.1.0-test27

Handles ServiceApp's decoder/network error event as well as native tune failure,
so DASH playback can retry the next format and return to radio on final failure.
Includes paired DASH/UHD support and yellow Search / blue YouTube from test26.

# 0.1.0-test26

Enables separate DASH video/audio pairing for high-resolution YouTube playback
when the registered Exteplayer/5002 backend and executable are available. Ranks
video formats by resolution, pairs every DASH candidate with audio, validates
both addresses and retains lower-quality/native fallbacks. The system MoviePlayer
and active skin remain. UHD requires a matching source and receiver support.
Yellow is now Search; blue is YouTube video, including captions in all languages.

# 0.1.0-test25

Adds current-song YouTube playback under yellow, with Favourite in MENU.
Uses the image's standard MoviePlayer and active skin for the information bar,
progress, position/duration/remaining time, video details, clock and native
controls. Removes the temporary two-line video overlay and its unused keymap
and translation. EOF, STOP and EXIT return to radio without a movie-list prompt;
external navigation and parent-close restoration remain guarded. Receiver
screenshots confirm test24 video playback. Prefers adaptive HLS/full quality range
and highest combined MP4 without the prior 720p limit; native failure retries a
lower validated format. Actual quality depends on video, receiver and connection.

# 0.1.0-test24 — unreleased receiver candidate

Adds current-song YouTube search, bundled source resolver/JavaScript interpreter
and native video playback under yellow. Favourite moves to MENU. Radio continues
during background lookup and resumes after video; stale results and external
navigation are guarded. All 21 locales include the new video messages. Public
search is verified; hosted playback is blocked by YouTube sign-in verification.
Candidate remains off the testing feed pending receiver playback confirmation.

# 0.1.0-test23

Removes the Playback activity caption beneath the spectrum, including the unused
widget and translation key in all 21 languages. Keeps the spectrum and panel
geometry. Includes all test22 metadata and artwork-query fixes.

# 0.1.0-test22

Repairs reversible Central European metadata damage for Slovak/Czech stations,
with UTF-8 first and explicit legacy charset headers respected. Removes numeric
file-track prefixes and replaces underscores with spaces for artwork queries
only. Recognizes the complete Rust2Dust band spelling and vs./vs punctuation.
Preserves remix/version words, shared lyrics identity and artwork match checks.
Artist artwork stays explicitly labelled when an exact song cover is unavailable.

# 0.1.0-test21

Accepts explicit Original Mix/Original Version tags when the catalogue omits
that default suffix. Uses a unique corroborated live-album cover when ICY omits
the performance suffix. Adds an early exact-artist iTunes artwork fallback,
labelled as artist artwork in all 21 languages. Fixes the receiver-reported BCC
Worship, Jackers Revenge and Dianah Kay cases. Preserves meaningful title
parentheses, displayed stream metadata and shared lyrics identity.

# 0.1.0-test20

Finds artwork when a broadcaster abbreviates a collaboration credit or omits a
descriptive song subtitle. Fixes the receiver-reported CHILL77 / PAPAOUTAI case.
Queries the default iTunes music catalogue first, with regional lookups retained
as fallbacks, so a usable first result avoids repeated regional searches.
Exact recording matches retain priority; unrelated artists and conflicting live,
remix, acoustic and instrumental versions are rejected. Lookup tracing is
available for diagnostics. Existing layout, metadata, languages and updates stay
unchanged.

# 0.1.0-test19

Uses PiconHub's subtly translucent navy panel fill for all three main panels and
the update progress window. Popup text backgrounds are transparent, avoiding
opaque rectangles over the shared fill. Text, artwork, borders and selected
country/menu/station rows remain fully visible. No layout or behaviour changes.

# 0.1.0-test18

Opens a modal progress window immediately after update approval, before starting
background I/O. Displays real download bytes/percentage, then package checking,
opkg installation and installed-state verification with activity feedback.
Successful verification shows the three-second notice and restarts GUI after
the modal window closes. Failures show the reason and restore controls without
restart. Worker progress is delivered through a bounded thread-safe mailbox;
GUI components are touched only on the GUI thread. All 21 locales updated.

# 0.1.0-test17

Replaces the upper Now playing/station-logo block with a 520px square current-song
cover or matching artist image. Station name, artist, title and country fit below
it. Complete recording identity is reused from FullHDGlass. Lookups run in a
separate worker; a bounded RAM cache, neutral fallback, provider credit and stale
request/decoder guards keep playback independent of optional artwork.

Removes the separate Playing row, extends all three panels, and displays seven
complete stations. The left menu starts higher with the spectrum beneath it.
Action/error feedback stays in that panel. Only the focused country value now
has the same blue selection background as a list row; its white caption remains
unchanged and only OK opens choices.

# 0.1.0-test16

UP from the first centre station row and RIGHT from any station now focus the
cyan country control without opening a dialog. Only OK opens country choices.
Focus is marked by cyan pointers around the country; the white Select country
caption stays unchanged. DOWN or RIGHT returns to the exact selected station.
Cancelling country choices returns to the focused country control. Left-menu
UP/DOWN retain the normal within-menu navigation fixed in test15.

# 0.1.0-test15

Restricts the UP country shortcut to the centre station list. In the left
function menu, UP/DOWN now stay within that menu and wrap normally between
first and last entries. RIGHT from the left still returns to stations; RIGHT
from any station and UP from the first station still open country choices.
Selection and playback are preserved. User confirmed test14's menu name and
playing-song information now display correctly on the receiver.

# 0.1.0-test14

Adds primary ICY StreamTitle reading using the bounded FullHDGlass reader.
Native Enigma2 tags are the fallback when ICY is unavailable or still loading. Background reads are bounded and throttled to 15 seconds; GUI
refreshes the returned text without blocking. ICY titles and announcements
retain priority. Changing station, stopping or closing discards stale results.
Supports UTF-8/legacy ICY text and the shared artist/title separator handling.
Streams that do not transmit titles retain the honest no-information message.
Installation clears only this plugin’s Python bytecode cache so the renamed
menu descriptor and updated code are reloaded after the GUI restart.

# 0.1.0-test13

Adds a thin cyan outline to each of the three main panels, matching the Warder
plugin family/PiconHub style. Native opaque edge widgets scale with resolution.
Panel sizes, positions, content and controls are unchanged. Retains the renamed
radio-warder-evolution package, FullHDGlass spectrum and three-second restart.

# 0.1.0-test12

The plugin and extensions menus now display Radio Warder Evolution. The
installed package is radio-warder-evolution and replaces the old warderradio
package. Test11 is the old-ID compatibility bridge for existing auto-updaters;
it switches to the separate v2 feed before test12 changes the package identity.

Replaces the cyan playback bars with the approved FullHDGlass multicolour
segmented spectrum and peak markers, reusing its exact transparent frames.
One native pixmap update per 100 ms; no per-segment canvas drawing. The shared
48-frame cache has a fixed decoded pixel budget. Hidden screens pause, idle
playback hides the animation, and an unavailable frame disables only the
optional visual. The main layout and station playback remain unchanged.
Includes test10's automatic GUI restart three seconds after a verified update.

# 0.1.0-test10

After a verified successful plugin update, display a localized information
message for three seconds and automatically restart the GUI. There is no
second confirmation. Failed updates leave the interface usable without a
restart. The initial confirmation before installing remains. All 21 languages
include the new message. Retains test9 menu placement and direct country selector.

# 0.1.0-test9

Moves Update below Settings as the sixth left-menu item and restores the four
colour buttons across the footer. INFO remains a manual-update shortcut.
RIGHT from any station and UP from the first row now open the country selector
immediately, without an extra OK. The focus marker appears only beside the cyan
country name; the white Select country caption remains unchanged. Cancelling
restores the exact selected station and playback continues.

# 0.1.0-test8

RIGHT now moves directly from any station row to the Select country control.
OK opens the selector; DOWN or RIGHT returns to the exact previous station
without scrolling or interrupting playback. RIGHT from the left function menu
still enters the station list. UP from the first station remains available.
The contextual remote-control hint is updated in all 21 languages. Native
regression coverage checks first, middle and last rows, cancel and playback
continuity.

# 0.1.0-test7

First release from the dedicated Evolution-by-Warder/Radio-Warder-Evolution
repository. Source, CI, IPK releases and future update feeds now live here.
Retains the requested white Select country label, cyan selectable country/arrow,
startup resume of the last played station and fifth footer INFO · Update action.
All 21 UI languages and existing user data remain supported.

Older builds continue to receive the identical migration IPK through their
original verified update URL; after installation and GUI restart the updater
uses this standalone repository. The old feed is advanced only after both new
and compatibility downloads are verified.

# 0.1.0-test6

Adds a fifth footer button, INFO · Update, for manual plugin updates. The four
existing colour actions are preserved and the footer uses five evenly spaced
slots. The Update control is a native clickable button with an INFO remote-key
shortcut. It uses the same verified update path as Settings. If an automatic
check is already running, pressing Update displays its result as a manual check
without launching a duplicate worker. The new label is translated in all 21
languages. Includes native footer placement, click/key routing and in-flight
check regression coverage.

# 0.1.0-test5

Moves the country heading entirely into the centre panel as Select country –
Slovakia ▾, translated for the selected UI language and current country. The
permanent down arrow indicates that the control opens a selection list. The
Select country label and separator are white, while the country and arrow are
cyan blue, including when focused. Remote focus adds a leading pointer. The duplicate left-panel heading is removed from
view. The Settings action remains Choose country and Now playing is unchanged.
Slovak and Czech country names are localized without changing catalogue IDs.

Opening Warder Radio now automatically resumes the user's last played radio
station from existing persistent history and selects it in its list. Fresh
catalogue data is preferred for that station identity, with the remembered entry
as fallback. First use remains idle until a station is selected. Resume makes
one attempt, does not rewrite history, and restores the previous TV service on
close. No playback is started during installation or plugin discovery.

The new strings are complete in all 21 UI languages. Includes native regression
coverage for startup resume, custom streams, failed starts, focused selector and
return to the previous TV service.

# 0.1.0-test4

Renames the first Settings action to Choose country, using the same translated
label and selector as the direct country button. This follow-up preserves the
published test3 build and advances the normal testing update feed.

# 0.1.0-test3

Replaces the repeated left-panel Warder Radio heading with the translated Country
label. The current country beside it becomes a native clickable button. UP from
the first station focuses it; OK opens the existing country/group selector, and
DOWN returns to the stations. The current choice is preselected. Selection is
saved without interrupting playback; cancel preserves the station and section.
Now playing remains in its approved position. Section headings for favourites,
history, recordings and search stay visible below the country selector.

Adds the two new labels in all 21 languages. Existing automatic updates and
catalogue data are preserved. Validation includes native Button signal handling,
remote focus navigation, selection/cancel/persistence and unchanged playback.

# 0.1.0-test2

Fixes the receiver-reported blank interface: explicit z-order keeps background
artwork and panels below live text, lists, picons and the activity canvas.
Panels are opaque, so the TV video no longer shows through them. The regression
now reproduces test1 using its exact published skin and replays native creation
order with additional static widgets included.

Adds all 21 languages used across FullHDGlass, GSU and PiconHub, with complete UI
and update messages, receiver-language selection, Albanian aliases and Persian
right alignment. The approved English subtitle is preserved.

Adds automatic update checks when opening the plugin and a manual menu action.
Uses the existing reviewed Warder updater adapted for this independent package,
with TLS verification, exact release URL, bounded size, SHA-256, IPK identity,
installed-file/version and opkg-status checks. Installation and GUI restart are
offered to the user. Test and stable channels are kept separate, and the testing
feed is advanced only after the public IPK has been downloaded and verified.

Still a receiver-test prerelease; physical display/audio/GLES verification is
pending. Existing favourites, history and custom stations are preserved.

# 0.1.0-test1

First independent Warder Radio receiver-test candidate. Implements the approved
three-column design, functions on the left and version after the clock, with the
approved transparent Warder-family plugin-browser icon.

Includes the complete current Warder/PiconHub bouquet (5,444 unique references in
203 groups), native radio playback, metadata, picons, favourites, history, local
search, custom stations, explicit catalogue refresh, recordings browser and
optional streamripper recording. English subtitle: **World of Radio Stations**.

No existing stable plugin, skin,
feed or global action mapping is changed. Runtime is pure Python 3.9+.

Validation: 15 unit tests plus 6 native replay cases on each of three pinned
OpenPLi/OpenATV source revisions; integral rows verified at HD/FHD/WQHD/UHD;
IPK payload and offline scripts verified. Hardware playback/GLES/remote test is
pending and this version is deliberately a prerelease.
