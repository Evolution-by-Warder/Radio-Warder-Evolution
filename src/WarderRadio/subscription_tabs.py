"""One-row native Enigma2 subscription tabs in the existing Radio content panel.

Use LEFT/RIGHT to choose a saved category or the always-visible Add control.
The category bar never downloads stations or handles playback itself.
"""
import enigma
import os
from enigma import eListboxPythonMultiContent, gFont
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend
from Tools.LoadPixmap import LoadPixmap
from . import ROOT

from .i18n import t


class SubscriptionTabs(MenuList):
    """Three visible category chips plus a pinned '+ Add subscription' chip."""

    def __init__(self, scale):
        self.scale = scale
        self.categories = []
        self.active = ''
        self.cursor = 0
        MenuList.__init__(self, [(0,)], True, eListboxPythonMultiContent)
        self.l.setItemHeight(max(1, round(64 * scale)))
        self.l.setFont(0, gFont('Regular', max(1, round(21 * scale))))
        self.l.setFont(1, gFont('Regular', max(1, round(27 * scale))))
        self.l.setBuildFunc(self.build)
        try:
            self.selected_chip = LoadPixmap(os.path.join(ROOT, 'artwork', 'ui', 'chip-selected.png'), cached=True)
        except (OSError, ValueError, TypeError):
            self.selected_chip = None

    def set_categories(self, categories, active):
        categories = list(categories)
        changed = categories != self.categories or active != self.active
        self.categories, self.active = categories, active
        if changed:
            self.cursor = categories.index(active) if active in categories else len(categories)
            self.redraw()
        else:
            self.cursor = min(self.cursor, len(categories))

    def redraw(self):
        invalidate = getattr(self.l, 'invalidate', None)
        if invalidate:
            invalidate()
        else:
            self.setList([(0,)])

    def move_cursor(self, delta):
        cursor = max(0, min(len(self.categories), self.cursor + delta))
        if cursor == self.cursor:
            return False
        self.cursor = cursor
        self.redraw()
        return True

    def chosen(self):
        return self.categories[self.cursor] if self.cursor < len(self.categories) else None

    def build(self, unused=0):
        def n(value):
            return max(1, round(value * self.scale))
        flags = enigma.RT_HALIGN_CENTER | enigma.RT_VALIGN_CENTER | getattr(enigma, 'RT_ELLIPSIS', 0)
        result = [None]

        if not self.categories:
            # An empty subscription screen must have an obvious first action.
            if self.selected_chip is not None:
                result.append(MultiContentEntryPixmapAlphaBlend(
                    pos=(n(8), n(7)), size=(n(594), n(48)),
                    png=self.selected_chip, flags=enigma.BT_SCALE))
            result.append(MultiContentEntryText(
                pos=(n(12), n(5)), size=(n(594), n(52)), font=1, flags=flags,
                text='+ ' + t('Add first subscription'),
                color=0x00ceff, color_sel=0x00ceff))
            return result

        first = max(0, min(max(0, self.cursor - 2), max(0, len(self.categories) - 3)))
        shown = self.categories[first:first + 3]
        for column, category in enumerate(shown):
            index = first + column
            focus = index == self.cursor
            current = category == self.active
            short = category[:11] + ('…' if len(category) > 11 else '')
            caption = ('› ' if focus else '● ' if current else '') + short
            if focus and self.selected_chip is not None:
                result.append(MultiContentEntryPixmapAlphaBlend(
                    pos=(n(8 + column * 150), n(7)), size=(n(145), n(48)),
                    png=self.selected_chip, flags=enigma.BT_SCALE))
            result.append(MultiContentEntryText(
                pos=(n(8 + column * 150), n(7)), size=(n(145), n(48)),
                font=0, flags=flags, text=caption,
                color=0x00ceff if focus else 0x4bc951 if current else 0xa6bed1,
                color_sel=0x00ceff if focus else 0x4bc951 if current else 0xa6bed1))
        if self.cursor == len(self.categories) and self.selected_chip is not None:
            result.append(MultiContentEntryPixmapAlphaBlend(
                pos=(n(462), n(7)), size=(n(151), n(48)),
                png=self.selected_chip, flags=enigma.BT_SCALE))
        result.append(MultiContentEntryText(
            pos=(n(462), n(7)), size=(n(151), n(48)), font=0, flags=flags,
            text='+ ' + t('Add subscription'),
            color=0x00ceff if self.cursor == len(self.categories) else 0xa6bed1,
            color_sel=0x00ceff if self.cursor == len(self.categories) else 0xa6bed1))
        return result
