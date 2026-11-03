# Warder Radio 0.1.0-test8 — verified standalone handoff

The owner created the public Radio-Warder-Evolution repository and authorized all setup. The independent project is now imported at its root with README, licence, source, approved artwork, full catalogue/provenance, tests, documentation, CI, releases and separate testing/stable update feeds.

Source: `9a5908f0464d5683aaef4b940839f44ed30956a5`.
Build/release CI: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/actions/runs/41624499197 — success.
Legacy bridge: https://github.com/Evolution-by-Warder/FullHDGlass-Warder-Evolution/actions/runs/41624775734 — success.

## Current behaviour

- RIGHT from any station focuses Select country; OK opens the selector. RIGHT or DOWN returns to exactly the same row and scroll position. LEFT from the list still opens the function panel; RIGHT from that panel returns to stations. Hints are localized.
- Country control sits in the centre only: white Select country/separator, cyan selected country and arrow. Settings uses Choose country. Now playing remains on the right.
- Opening resumes the user's last played radio station, preferring refreshed catalogue data. Fresh users remain idle. Closing restores the previous service when still owned.
- Footer retains the four colour actions and adds native INFO · Update. INFO/click/manual Settings checks share the verified updater, with no duplicate check if an automatic request is in flight.
- All 21 languages contain all 67 UI strings. Catalogue: 5,444 station references in 203 country/themed groups; no identity/classification rewrite. Favourites, history, custom stations and optional recording are retained.

## Verification and distribution

25 unit cases plus 15 native cases on each of three pinned OpenPLi/OpenATV revisions: 70 executions. Package verification and public downloads passed.

IPK: 2,798,248 bytes; SHA-256 `5d9f3dd951baf1ff0fd052b750a397d5322dbe199b1a08ecfd3e5c6a9a79d5a5`.

New repository and legacy release URLs both serve identical verified bytes. End-to-end checking as installed test6 offers test8 through the old feed; checking test7 offers test8 through the new feed. The migration IPK embeds the new repository updater. Archived legacy radio builds were retired so they cannot replace the migration feed with an older version. Other plugin/skin production feeds are unaffected. Radio stable feed is empty pending approval.

Release: https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/tag/warder-radio-v0.1.0-test8

## Repository metadata limitation

README/project description and documentation are completed. The About field still reads Warder Radio - World of Radio Stations; homepage/topics remain unset. An authorized one-time About update was attempted in Actions but GitHub returned HTTP 403 Resource not accessible by integration (token metadata permission is read-only). No success is claimed for that field. The owner was given the exact local PowerShell/gh command; tools/set-repository-about.ps1 contains the same reviewed setup operation for description, release homepage and topics. The unsupported Actions metadata attempt was removed from future builds.

Physical receiver confirmation of the new RIGHT shortcut is pending. Native replay stubs the C++/OS boundary; screenshots already show the mixed header colours and five footer controls rendering on the test6 receiver.
