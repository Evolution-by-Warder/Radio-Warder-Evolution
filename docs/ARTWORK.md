# Current-song artwork (test20)

The upper player block is a square cover, followed by a compact station name,
artist, title and country. At Full HD the cover is 520x520; native layout scales
it for HD/WQHD/UHD and ePicLoad preserves image aspect. The spectrum is below
the raised function menu in the left panel. All panels extend to y=994, with
seven whole station rows and no separate full-width Playing label.

Song lookup first queries the default iTunes catalogue with `media=music` and
`limit=20`, over HTTPS. SK/CZ queries and a bounded title search remain fallbacks;
a separate US query would duplicate the default catalogue. Exact recording
matches rank first. For artwork only, complete credited artist names may also
match an abbreviated ICY credit, and a missing descriptive parenthesized title
suffix may be tolerated. Live, remix, acoustic, instrumental and other different
versions are rejected when absent from the requested title. The shared exact
FullHDGlass identity and metadata displayed to the listener are unchanged.
When no song cover is found, an entire-artist-credit TheAudioDB match may supply an
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

## Verified short-credit case

The receiver reported CHILL77 / PAPAOUTAI. The public iTunes API returned
mikeeysmind, Chill77 & Unjaps / Papaoutai (Afro Soul) as the first result, with an
Apple image URL. Test19 rejected that result even though both its regional query
and the global query returned it. The fixed artwork ranking accepts that result
while rejecting the accompanying remix and unrelated performer. A successful
first result requires one catalogue request plus one image download. The measured
query durations are from a hosted runner, not a receiver performance guarantee.

The separate public-query comparison is read-only and does not execute or trace
a receiver plugin. Its report records requested/final URLs, timing, catalogue
results and test19 acceptance decisions:
https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41652995750

The test20 publication check also downloaded the real cover in two requests:
https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41652995788

Optional `lookup_cover(..., trace=callback)` diagnostics report requests,
responses, candidate rankings and the selected image URL. Callback errors are
isolated, and normal playback supplies no trace callback.
