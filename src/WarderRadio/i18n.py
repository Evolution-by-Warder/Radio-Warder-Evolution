"""Complete translations shared across the Warder plugin language set."""
import json
import os
from . import ROOT

SUPPORTED = ('al', 'cs', 'de', 'el', 'en', 'es', 'et', 'fa', 'fr', 'hu', 'it',
             'lt', 'nl', 'pl', 'pt', 'ro', 'ru', 'sk', 'tr', 'uk', 'zh')
_CACHE = {}

# New optional main-menu controls (all supported receiver languages).
_MAIN_MENU_TEXT = {
    "al": {
        "Show in Enigma2 main menu": "Shfaq në menynë kryesore Enigma2",
        "Main menu setting saved": "Cilësimi i menysë kryesore u ruajt",
        "Could not save setting": "Nuk u ruajt cilësimi"
    },
    "cs": {
        "Show in Enigma2 main menu": "Zobrazit v hlavním menu Enigma2",
        "Main menu setting saved": "Nastavení hlavního menu bylo uloženo",
        "Could not save setting": "Nastavení se nepodařilo uložit"
    },
    "de": {
        "Show in Enigma2 main menu": "Im Enigma2-Hauptmenü anzeigen",
        "Main menu setting saved": "Hauptmenü-Einstellung gespeichert",
        "Could not save setting": "Einstellung konnte nicht gespeichert werden"
    },
    "el": {
        "Show in Enigma2 main menu": "Εμφάνιση στο κύριο μενού Enigma2",
        "Main menu setting saved": "Η ρύθμιση του κύριου μενού αποθηκεύτηκε",
        "Could not save setting": "Δεν ήταν δυνατή η αποθήκευση της ρύθμισης"
    },
    "en": {
        "Show in Enigma2 main menu": "Show in Enigma2 main menu",
        "Main menu setting saved": "Main menu setting saved",
        "Could not save setting": "Could not save setting"
    },
    "es": {
        "Show in Enigma2 main menu": "Mostrar en el menú principal de Enigma2",
        "Main menu setting saved": "Ajuste del menú principal guardado",
        "Could not save setting": "No se pudo guardar el ajuste"
    },
    "et": {
        "Show in Enigma2 main menu": "Kuva Enigma2 peamenüüs",
        "Main menu setting saved": "Peamenüü säte salvestatud",
        "Could not save setting": "Seadet ei saanud salvestada"
    },
    "fa": {
        "Show in Enigma2 main menu": "نمایش در منوی اصلی Enigma2",
        "Main menu setting saved": "تنظیم منوی اصلی ذخیره شد",
        "Could not save setting": "تنظیم ذخیره نشد"
    },
    "fr": {
        "Show in Enigma2 main menu": "Afficher dans le menu principal Enigma2",
        "Main menu setting saved": "Paramètre du menu principal enregistré",
        "Could not save setting": "Impossible d’enregistrer le paramètre"
    },
    "hu": {
        "Show in Enigma2 main menu": "Megjelenítés az Enigma2 főmenüben",
        "Main menu setting saved": "Főmenü beállítása mentve",
        "Could not save setting": "A beállítás nem menthető"
    },
    "it": {
        "Show in Enigma2 main menu": "Mostra nel menu principale Enigma2",
        "Main menu setting saved": "Impostazione del menu principale salvata",
        "Could not save setting": "Impossibile salvare l'impostazione"
    },
    "lt": {
        "Show in Enigma2 main menu": "Rodyti pagrindiniame Enigma2 meniu",
        "Main menu setting saved": "Pagrindinio meniu nustatymas išsaugotas",
        "Could not save setting": "Nepavyko išsaugoti nustatymo"
    },
    "nl": {
        "Show in Enigma2 main menu": "Tonen in het Enigma2-hoofdmenu",
        "Main menu setting saved": "Hoofdmenu-instelling opgeslagen",
        "Could not save setting": "Kan instelling niet opslaan"
    },
    "pl": {
        "Show in Enigma2 main menu": "Pokaż w menu głównym Enigma2",
        "Main menu setting saved": "Zapisano ustawienie menu głównego",
        "Could not save setting": "Nie udało się zapisać ustawienia"
    },
    "pt": {
        "Show in Enigma2 main menu": "Mostrar no menu principal do Enigma2",
        "Main menu setting saved": "Definição do menu principal guardada",
        "Could not save setting": "Não foi possível guardar a definição"
    },
    "ro": {
        "Show in Enigma2 main menu": "Afișează în meniul principal Enigma2",
        "Main menu setting saved": "Setarea meniului principal a fost salvată",
        "Could not save setting": "Setarea nu a putut fi salvată"
    },
    "ru": {
        "Show in Enigma2 main menu": "Показывать в главном меню Enigma2",
        "Main menu setting saved": "Настройка главного меню сохранена",
        "Could not save setting": "Не удалось сохранить настройку"
    },
    "sk": {
        "Show in Enigma2 main menu": "Zobraziť v hlavnom menu Enigma2",
        "Main menu setting saved": "Nastavenie hlavného menu bolo uložené",
        "Could not save setting": "Nastavenie sa nepodarilo uložiť"
    },
    "tr": {
        "Show in Enigma2 main menu": "Enigma2 ana menüsünde göster",
        "Main menu setting saved": "Ana menü ayarı kaydedildi",
        "Could not save setting": "Ayar kaydedilemedi"
    },
    "uk": {
        "Show in Enigma2 main menu": "Показувати в головному меню Enigma2",
        "Main menu setting saved": "Налаштування головного меню збережено",
        "Could not save setting": "Не вдалося зберегти налаштування"
    },
    "zh": {
        "Show in Enigma2 main menu": "在 Enigma2 主菜单中显示",
        "Main menu setting saved": "主菜单设置已保存",
        "Could not save setting": "无法保存设置"
    }
}



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
    lang = language_code()
    return _MAIN_MENU_TEXT.get(lang, {}).get(text, translations(lang).get(text, text))


def rtl():
    return language_code() == 'fa'


def group_label(group):
    """Translate display names while retaining catalogue group identities."""
    names = {'Slovensko': 'Slovakia', 'Čechy': 'Czechia', 'Custom': 'Custom'}
    return t(names[group]) if group in names else group
