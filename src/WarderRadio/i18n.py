"""Complete translations shared across the Warder plugin language set."""
import json
import os
from . import ROOT

SUPPORTED = ('al', 'cs', 'de', 'el', 'en', 'es', 'et', 'fa', 'fr', 'hu', 'it',
             'lt', 'nl', 'pl', 'pt', 'ro', 'ru', 'sk', 'tr', 'uk', 'zh')
_CACHE = {}


def language_code(value=None):
    if value is None:
        try:
            from Components.Language import language
            value = language.getLanguage()
        except (ImportError, AttributeError):
            value = 'en'
    code = str(value or 'en').lower().replace('-', '_').split('_', 1)[0]
    code = {'sq': 'al', 'cz': 'cs'}.get(code, code)
    return code if code in SUPPORTED else 'en'


def translations(code):
    code = language_code(code)
    if code not in _CACHE:
        with open(os.path.join(ROOT, 'locale', code + '.json'), encoding='utf-8') as handle:
            _CACHE[code] = json.load(handle)
    return _CACHE[code]


def t(text):
    return translations(language_code()).get(text, text)


def rtl():
    return language_code() == 'fa'


def group_label(group):
    """Translate display names while retaining catalogue group identities."""
    names = {'Slovensko': 'Slovakia', 'Čechy': 'Czechia', 'Custom': 'Custom'}
    return t(names[group]) if group in names else group
