# Current-song YouTube video — receiver candidate

Unreleased test24 candidate. The testing updater continues to offer test23 until
receiver stream playback is confirmed.

Yellow now searches the currently playing station's artist/title and starts the
first organic YouTube video result. File underscores/track-number prefixes are
cleaned for the query; remix/version words remain. Favourite remains in MENU.
Radio continues while a dedicated worker searches/resolves. Changes of station,
song or screen generation invalidate stale results. Missing metadata, search
failure or a playback refusal leaves radio running and displays a reason.

The video surface uses native Enigma2 service 4097. EXIT/red/STOP returns to the
radio, green/play-pause toggles playback, left/right seeks ten seconds when
supported, OK toggles the overlay. EOF/failure also returns to radio. Navigation
ownership guards preserve an external channel change. Closing the parent screen
returns to the pre-plugin service rather than leaving a hidden radio stream.
Existing timers and worker queues are closed when the plugin exits.

Search reads at most 3 MiB of public YouTube result HTML and parses ytInitialData
as JSON, without evaluating page scripts. A common 30-second I/O deadline,
five-second socket timeouts, verified TLS and YouTube/Googlevideo origin checks
bound search and resolver page reads. The resolver is bundled as Python source,
independent of optional external plugins. Its GPL-2.0 upstream revision, changes
and full license are in youtube_engine/NOTICE and COPYING.GPLv2. Image-global
SSL verification and YouTube configuration are never changed. No API key,
cookies, account login, JavaScript runtime installation or video download is used.

Combined MP4 formats are preferred up to 720p. HLS master playback lets the
receiver choose compatible video/audio streams. Separate suburi tracks are
rejected. Actual codec support and seeking depend on the receiver image.

Verification: native widget/action/service replays cover all four resolutions,
yellow/menu behavior, radio continuation during lookup, stale callbacks, error,
EOF, return, parent close and external channel preservation. Unit fixtures cover
organic results, input cleanup, limits/TLS, the actual bundled resolver and JS
interpreter, current-client fallback and sign-in refusal.

Live public search found Jason Derulo's Want to Want Me (Westfunk Remix), video
buKVq_FBdxI. The hosted runner received LOGIN_REQUIRED / Sign in to confirm you
are not a bot from Android, VisionOS and iOS playback clients, with zero media
formats. Playback therefore has NOT been confirmed by this server test. This
does not establish what a residential receiver connection will return. The
candidate is retained on its review branch pending receiver verification.

Read-only live check:
https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41669798968
Public resolver source:
https://github.com/Taapat/enigma2-plugin-youtube/tree/15a7fba89b63476177ac083b032ee499262f64fb
Current public client-profile reference:
https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/youtube/_base.py
