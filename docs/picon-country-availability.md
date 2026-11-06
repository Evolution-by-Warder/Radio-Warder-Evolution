# Online picon country availability (working integration)

The picker contains all 219 countries from the Radio catalogue. The separate HDF
source view is not a country. Countries stay visible when no picons have been
published. Such rows show Unavailable and cannot be newly selected. Saved
selections remain intact, including a temporarily unavailable country.

The online index is
`https://raw.githubusercontent.com/Evolution-by-Warder/PiconHub-Warder-Evolution/main/picons/radio-world/catalog/countries.json`.
It declares coverage and a SHA-256/byte-count checked, immutable country release
manifest for each available country. Partial countries are downloadable. A newly
published country becomes selectable after reopening the picker; downloading
also refreshes availability. No plugin code or IPK change is required for country
publication. A future country added to both online catalogues is supported too.

All network work runs on I/O workers. A valid index is cached atomically. A failed,
incomplete or malformed refresh retains the last valid index; a fresh installation
has a bundled snapshot describing only already published packages. The GUI shows
when saved availability is being used. Stale callbacks cannot reopen a closed
picker. An unavailable selection is skipped explicitly in the download log.

The downloader requests **only 220×132**, in the selected transparent, white or
black background. 50×30 and 400×240 remain GitHub assets for future use. The online
index cannot change this receiver limit. Shared SK/CZ archives are downloaded
once. Country/service filtering, ZIP and PNG verification, free-space checks,
cancellation, flat storage, legacy migration and custom-image preservation remain
in force. Existing setting paths, keys and selected country codes are preserved.

## Publication order

1. Review and approve the Radio-only PiconHub work branch.
2. Publish country payloads and their pinned release manifests, then regenerate
   `picons/radio-world/catalog/countries.json` with `build_country_index.py` against
   that exact manifest commit. The builder computes coverage from the current
   country catalogue and inventories common to all three 220×132 backgrounds.
3. Confirm that the live index, release manifests and ZIPs pass the integration
   replay. Merge the plugin only after explicit approval.
4. Obtain separate approval to issue the IPK. Local builds and native-widget
   replays are not physical receiver verification.

The staged online index and the plugin's bundled published snapshot deliberately
have different availability until package publication is approved. Neither the
stable nor testing update feed is changed by this work.
