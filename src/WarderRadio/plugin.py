"""Lazy plugin entry: no network, playback or firmware changes at discovery."""
from Plugins.Plugin import PluginDescriptor
from .i18n import t


def main(session, **kwargs):
    from .screen import WarderRadio
    session.open(WarderRadio)


def Plugins(**kwargs):
    return [PluginDescriptor(name='Warder Radio', description='World of Radio Stations',
                             where=PluginDescriptor.WHERE_PLUGINMENU, icon='plugin.png', fnc=main),
            PluginDescriptor(name='Warder Radio', description='World of Radio Stations',
                             where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=main)]
