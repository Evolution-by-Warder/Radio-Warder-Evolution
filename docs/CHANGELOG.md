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

No HDF Radio executable/bytecode is included. No existing stable plugin, skin,
feed or global action mapping is changed. Runtime is pure Python 3.9+.

Validation: 15 unit tests plus 6 native replay cases on each of three pinned
OpenPLi/OpenATV source revisions; integral rows verified at HD/FHD/WQHD/UHD;
IPK payload and offline scripts verified. Hardware playback/GLES/remote test is
pending and this version is deliberately a prerelease.
