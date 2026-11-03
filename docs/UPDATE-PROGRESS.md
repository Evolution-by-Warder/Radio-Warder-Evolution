# Update progress (test18)

After the existing install confirmation, the controller opens a native modal
window in the Warder dark/cyan style. Only its next GUI timer event submits I/O,
so the popup exists before download/installation begins. While updating,
OK/EXIT cannot dismiss the dialog or close the underlying screen.

The download bar and percentage are calculated from actual bytes/manifest size.
Download reports use 32 KiB chunks. Subsequent package verification, opkg install
and installed-state verification show the current phase with an animated activity
indicator. Those phases have no reliable percentage; the download bar/percentage
are hidden rather than presenting invented installation percentages.

The worker reports to a locked single-slot mailbox; fast chunks coalesce rather
than queueing unlimited GUI events. The existing GUI poll alone updates native
widgets. Successful opkg execution is insufficient on its own: installed package
status and all required runtime files must also verify before success is shown.

After verified success, the same modal displays the translated three-second
restart notice and a final 100% bar. A single-shot timer closes it with success;
only its close callback can open the standard GUI restart path. Failure stops
the busy timer, shows Update failed and the bounded tail of the reason, enables
parent controls and permits OK/EXIT to return. It never arms GUI restart.

All 21 locales have 71 complete UI keys. ProgressBar and VariableValue native
sources are hash-pinned for the same three OpenPLi/OpenATV fixture commits.
Tests cover open-before-I/O ordering, real percentages and stages, disabled
cancellation, success-after-verification, failure return, duplicate callbacks,
cleanup, both timer APIs and HD/FHD/WQHD/UHD geometry.

The new UI is used by updates started from test18 or later. The one-time upgrade
from test17 still runs its already-loaded old updater; installing test18 manually
and restarting GUI is also supported. The immutable test11 package-name bridge
and other products' feeds are unchanged. Receiver confirmation is pending.
