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
