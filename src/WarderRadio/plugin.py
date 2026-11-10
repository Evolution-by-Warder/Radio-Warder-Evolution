"""Lazy plugin entry: no network, playback or firmware changes at discovery."""
from Plugins.Plugin import PluginDescriptor

from .i18n import t


def main(session, **kwargs):
    from .screen import WarderRadio
    session.open(WarderRadio)


def main_menu(menuid, **kwargs):
    """Enigma2 menu extension; evaluated when the main menu is built."""
    if menuid != 'mainmenu':
        return []
    # Read only the small state document; do not initialize audio or GUI at discovery.
    from .model import read_json
    state = read_json('/etc/enigma2/warder-radio/state.json', {}, 512 * 1024)
    if not isinstance(state, dict) or state.get('show_main_menu') is not True:
        return []
    return [(t('Radio by Warder'), main, 'warder_radio_mainmenu', 55)]


def Plugins(**kwargs):
    return [PluginDescriptor(name='Radio Warder Evolution', description='World of Radio Stations',
                             where=PluginDescriptor.WHERE_PLUGINMENU, icon='plugin.png', fnc=main),
            PluginDescriptor(name='Radio Warder Evolution', description='World of Radio Stations',
                             where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=main),
            PluginDescriptor(name='Radio by Warder', description='Optional main menu entry',
                             where=PluginDescriptor.WHERE_MENU, fnc=main_menu)]
