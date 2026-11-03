# Dedicated repository and update migration

The owner created the public repository
Evolution-by-Warder/Radio-Warder-Evolution with main as its default branch.
The project is imported at the root, with its own GitHub Actions build and
release workflow in .github/workflows/radio-test.yml.

New packages use this repository's main/update/testing.json or stable.json,
depending on the installed channel. The catalogue still comes from the owned
PiconHub bouquet; station identities and user settings are unchanged.

Installed test1–test6 packages validate exact FullHDGlass-hosted release URLs.
Their update manifest must therefore continue to offer a verified migration IPK
at the old URL. The bridge publishes the identical IPK from this repository,
verifies both downloads and advances the old feed only afterwards. Following
installation and GUI restart, the embedded updater uses this standalone repo.
Do not replace old manifest URLs with foreign URLs that older updaters reject.

The existing FullHDGlass, GSU and PiconHub production updates are independent
of this radio migration. Radio remains in its testing channel pending receiver
acceptance; the stable radio feed is empty.
