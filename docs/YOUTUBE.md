# Current-song YouTube video — test27

Receiver screenshots confirm test24's actual YouTube video playback. Test25
retains that resolver and uses the image's standard Screens.InfoBar.MoviePlayer
with the active MoviePlayer skin. The image supplies its information bar,
progress, elapsed/remaining/total time, aspect, resolution/quality, clock and
native playback controls according to available metadata and skin design.

Blue searches the playing station's artist/title and starts the first organic
YouTube result. File underscores and track-number prefixes are cleaned for the
query; remix/version words remain. Favourite is in MENU. Radio continues during
background lookup. Song/station/screen generations discard stale results. A
missing song, search failure or playback refusal leaves radio running and shows
a reason. The plugin does not add sign-in or confirmation screens.

Native STOP/EXIT and EOF return directly to radio. The image's normal pause,
seek, audio/subtitle and info-bar controls are inherited. A pre-close ownership
guard preserves external navigation and returns to the pre-plugin service if
the parent closes. The adapter leaves the native close handler in place. On
images exposing fromMovieSelection it passes False, and transient-stream resume
prompts are disabled. The custom two-line video overlay/keymap is removed.

Search reads at most 3 MiB of public result HTML and parses ytInitialData as JSON.
A common 30-second I/O deadline, five-second socket timeouts, verified TLS and
YouTube/Googlevideo origin checks bound search/resolver reads. The GPL-2.0 source
resolver/interpreter are bundled; upstream revision, local changes and full
license are in youtube_engine/NOTICE and COPYING.GPLv2. Image-global TLS and
YouTube settings are untouched. No API key, cookies, account login, external
plugin installation, JavaScript runtime installation or video download is used.
DASH pairs precede HLS/combined fallbacks when supported; otherwise adaptive HLS
is preferred when available, exposing its quality range to the native demuxer. DASH video-only formats are ranked by resolution and paired with audio when
both the exteplayer3 executable and registered 5002 service are available.
Every component of a video&suburi=audio pair must be a validated Googlevideo HTTPS
URL. A DASH candidate without audio is rejected. Up to eight paired/combined/HLS
choices are retained. Pairs use Exteplayer service 5002; combined/HLS use 4097.
Playback failure advances to the next option while preserving radio return.
There is no forced installation or change to image-global backend settings.
Yellow is station Search; blue is YouTube, with captions following the language.
Actual quality depends on available formats, receiver codecs and connection.

Native replays cover blue/yellow/menu handling, radio continuation, stale callbacks,
constructor signatures, skin selection, EOF/failure/exit and external/parent-close
restoration on three pinned image revisions. Actual UI/mixin constructors and
C++ rendering are outside these replays; native MoviePlayer close handlers are
executed from the pinned upstream files. Receiver verification of the new native
information-bar layout remains necessary.

Hosted public search found the expected Westfunk remix. Player API requests from
the hosted runner returned anti-bot LOGIN_REQUIRED responses. That does not
contradict the later receiver screenshots showing successful playback. A passing
server workflow alone must not be described as real receiver playback evidence.

Read-only hosted check:
https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41669798968
Source resolver:
https://github.com/Taapat/enigma2-plugin-youtube/tree/15a7fba89b63476177ac083b032ee499262f64fb
Current client-profile reference:
https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/youtube/_base.py
