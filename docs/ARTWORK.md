# Current-song artwork (test17)

The upper player block is a square cover, followed by a compact station name,
artist, title and country. At Full HD the cover is 520x520; native layout scales
it for HD/WQHD/UHD and ePicLoad preserves image aspect. The spectrum is below
the raised function menu in the left panel. All panels extend to y=994, with
seven whole station rows and no separate full-width Playing label.

Song lookup reuses FullHDGlass warderSongIdentity: complete recording/artist
credits, known curated aliases, regional SK/CZ/US iTunes searches, then a bounded
title search. It does not accept arbitrary first or partial search hits. When
no song cover is found, an entire-artist-credit TheAudioDB match may supply an
artist thumb. Unknown metadata, announcements or missing artwork show the
approved neutral Warder graphic. Provider credit appears beneath loaded images.

Sources:
- https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/Searching.html
- https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/UnderstandingSearchResults.html
- https://www.theaudiodb.com/docs_json
- https://www.theaudiodb.com/docs_artwork

One dedicated artwork worker performs bounded network reads, separate from
playback, ICY and plugin updates. Requests have a common 18-second deadline,
per-read timeouts, 1 MiB JSON and 4 MiB image limits. Generated JPEG cache files
are restricted to /tmp/warder-radio-covers, with at most 64 entries/16 MiB.
Failed searches retry at most once after 60 seconds for the same song.
The GUI poll handles results; source generations and decoder tokens reject old
results immediately after a song/station change or close. Native ePicLoad signal
APIs are both supported. Optional image/decoder failure must not break radio.

Country caption and value are separate native components. The rendered caption
width positions the country field per locale, bounded to the centre panel.
The selected value uses list-selection blue, while Select country stays white
on the regular panel background. Arrows focus only, OK opens country choices.

Automated fixtures validate lookup identity, artist fallback, limits/cache,
decoder errors and late callbacks; actual broadcaster/provider availability and
receiver image/GLES composition require user testing. Artwork is downloaded on
demand and is not distributed in the IPK. No new translation keys are needed;
provider credits are proper names and all 21 language catalogues are retained.
