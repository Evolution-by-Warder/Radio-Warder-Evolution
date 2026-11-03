# Standalone Warder Radio import

The owner created Evolution-by-Warder/Radio-Warder-Evolution and authorized the
source import, description and all related setup. GitHub metadata confirmed a
public repository, main default branch and write access. The initially empty
repository was initialized through the GitHub connector with a README.

The project is imported at its own root, including the approved artwork, full
catalogue/provenance, native replay fixtures, tests, documentation, GPL license,
CI workflow and independent testing/stable update manifests. New test7 packages
point to this repository. A verified compatibility release will keep old
FullHDGlass-hosted updater URLs working for installed radio packages.

Current features: centre Select country label in white, selectable country and
arrow in cyan blue, native direct selector, last-played station resume, native
footer INFO · Update manual action, automatic update checks, 21 complete UI
languages, favourites/history/custom stations, picons and optional recording.

Validation before import: 25 unit cases and 14 native cases on each of three
pinned upstream revisions, 67 executions, plus IPK payload verification. New
repository CI/release and compatibility feed verification are recorded after
publication. Receiver confirmation of new footer/colours/resume is pending.

GitHub connector has no repository-metadata setter. The optional local
PowerShell command in tools/set-repository-about.ps1 contains the requested
public About description, release homepage and topics. It does not change
visibility, permissions or credentials. README and project documentation are
updated through the connector independently of the About metadata field.
