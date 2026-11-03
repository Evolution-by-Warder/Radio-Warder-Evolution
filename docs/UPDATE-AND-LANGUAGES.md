# Test2: display fix, shared languages and automatic updates

The screenshot from test1 showed static artwork but no live controls. The
original skin used default z-position for every widget; native Screen creates
additional static widgets after named components, and equal-z siblings are
inserted after existing children. This put the full-screen background above
live content. The replay originally skipped static widgets and therefore missed
this paint-order defect.

Test2 assigns background z=0, opaque panels z=1 and live controls z=2. The native
replay now instantiates additional static widgets, reproduces the failure from
the exact published test1 skin, and checks that the corrected live elements are
above all overlapping background widgets. TV video no longer shows through the
panels. Native replay still does not replace a physical receiver/GLES check.

Language coverage is the union of FullHDGlass's 19 translated locales, GSU's
English and other locales, and PiconHub's Greek: 21 languages. All 60 UI/message
keys are supplied per language. Albanian accepts al/sq, Czech accepts cs/cz,
regional codes resolve to their language, and Persian UI labels align right.
The fixed English brand subtitle remains World of Radio Stations.

The backend is adapted from the existing reviewed Warder updater at
PiconHub-Warder-Evolution/main/plugin/src/Plugins/Extensions/WarderPiconHub/warder_update.py
retrieved for this change. It uses namedtuple rather than dataclasses for
receiver compatibility. The new package has its own product identity, exact
GitHub release URL, version semantics and separate testing/stable manifests.

Each plugin opening schedules a background update check. MENU provides a manual
check. A found update is offered for confirmation. Download size, SHA-256, IPK
package identity/architecture/version, installed payload and final opkg status
are verified. Installation runs off the GUI thread and disables this screen's
controls while active; success displays a localized information message for three seconds and then
automatically restarts the GUI. No second confirmation is needed; failed
updates restore the controls without restarting. No forced installation or
restart is performed. Test2 must be installed manually over test1, which did not
have the updater. Subsequent testing updates use the testing feed.

CI publishes the prerelease and downloads its public IPK to verify the exact
bytes before updating update/testing.json. Stable feed remains empty until a
stable release is approved. Existing FullHDGlass, GSU and PiconHub feeds are not
part of this change.

Validation: 25 unit cases, nine native replay cases on each of three pinned
OpenPLi/OpenATV revisions (52 executions), and package payload/install-script
verification. Hardware confirmation is pending.

## Package rename in test12

The browser name is Radio Warder Evolution. The canonical opkg ID is
enigma2-plugin-extensions-radio-warder-evolution, replacing/conflicting with
enigma2-plugin-extensions-warderradio. Owned files and settings paths are retained.
The new updater uses update/v2/testing.json and update/v2/stable.json.
The original testing.json serves the immutable old-ID test11 bridge because
installed old updaters strictly validate that identity. Following GUI restart,
the bridge offers the canonical test12 through v2. A direct test12 installation
performs the rename in one opkg operation. Both public packages are verified
before either feed is committed. Initial install confirmation remains; successful
updates show a three-second notice and automatically restart the GUI.
