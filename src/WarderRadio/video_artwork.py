"""Optional local artwork beside the native video information bar."""
import os

from enigma import ePicLoad, getDesktop
from Components.Pixmap import Pixmap
from Screens.Screen import Screen

from .cover_display import CoverDisplay


def image_file(path):
    return (isinstance(path, str) and os.path.isabs(path)
            and path.lower().endswith(('.jpg', '.jpeg', '.png')) and os.path.isfile(path))


def placement(player):
    desktop = getDesktop(0).size()
    width, height = desktop.width(), desktop.height()
    scale = min(width / 1920.0, height / 1080.0)
    side, gap = max(1, round(240 * scale)), max(1, round(12 * scale))
    # Bottom-anchored MoviePlayer skins expose the bar's top as window position.
    # Full-screen skins use a conservative area above their bottom controls.
    bar_top = round(height * .73)
    try:
        top = player.instance.position().y()
        if top >= height // 3:
            bar_top = top
    except (AttributeError, RuntimeError, TypeError):
        pass
    return (min(round(80 * scale), max(0, width - side)),
            max(0, min(height - side, bar_top - side - gap)), side)


class VideoArtwork(Screen):
    """Non-modal, transparent, no keys and no service/navigation ownership."""
    def __init__(self, session, path, rectangle):
        x, y, side = rectangle
        self.skin = ('<screen name="WarderRadioVideoArtwork" position="%d,%d" '
                     'size="%d,%d" zPosition="10" flags="wfNoBorder" backgroundColor="#ff000000">'
                     '<widget name="image" position="0,0" size="%d,%d" '
                     'alphatest="blend" scale="1" /></screen>' % (x, y, side, side, side, side))
        Screen.__init__(self, session)
        self.path = path
        self['image'] = Pixmap()
        self.display = CoverDisplay(self['image'], ePicLoad, path)
        self.onLayoutFinish.append(self.ready)
        self.onClose.append(self.release)

    def ready(self):
        self.set_artwork(self.path)

    def set_artwork(self, path):
        if not image_file(path) or self.display.closed:
            self['image'].hide()
            return
        self.path = path
        self.display.fallback = path  # A failed new decode never restores old artwork.
        self.display.show(path)

    def release(self):
        self.display.close()
