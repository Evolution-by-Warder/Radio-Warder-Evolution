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
        "Main menu setting saved": "Cilësimi i menysë kryesore u ruajt. Rinisni GUI-n.",
        "Could not save setting": "Nuk u ruajt cilësimi"
    },
    "cs": {
        "Show in Enigma2 main menu": "Zobrazit v hlavním menu Enigma2",
        "Main menu setting saved": "Nastavení hlavního menu bylo uloženo. Restartujte GUI.",
        "Could not save setting": "Nastavení se nepodařilo uložit"
    },
    "de": {
        "Show in Enigma2 main menu": "Im Enigma2-Hauptmenü anzeigen",
        "Main menu setting saved": "Hauptmenü-Einstellung gespeichert. Bitte GUI neu starten.",
        "Could not save setting": "Einstellung konnte nicht gespeichert werden"
    },
    "el": {
        "Show in Enigma2 main menu": "Εμφάνιση στο κύριο μενού Enigma2",
        "Main menu setting saved": "Η ρύθμιση κύριου μενού αποθηκεύτηκε. Επανεκκινήστε το GUI.",
        "Could not save setting": "Δεν ήταν δυνατή η αποθήκευση της ρύθμισης"
    },
    "en": {
        "Show in Enigma2 main menu": "Show in Enigma2 main menu",
        "Main menu setting saved": "Main menu setting saved. Please restart the GUI.",
        "Could not save setting": "Could not save setting"
    },
    "es": {
        "Show in Enigma2 main menu": "Mostrar en el menú principal de Enigma2",
        "Main menu setting saved": "Ajuste del menú principal guardado. Reinicie la GUI.",
        "Could not save setting": "No se pudo guardar el ajuste"
    },
    "et": {
        "Show in Enigma2 main menu": "Kuva Enigma2 peamenüüs",
        "Main menu setting saved": "Peamenüü säte salvestatud. Taaskäivitage GUI.",
        "Could not save setting": "Seadet ei saanud salvestada"
    },
    "fa": {
        "Show in Enigma2 main menu": "نمایش در منوی اصلی Enigma2",
        "Main menu setting saved": "تنظیم منوی اصلی ذخیره شد. رابط کاربری را دوباره راه‌اندازی کنید.",
        "Could not save setting": "تنظیم ذخیره نشد"
    },
    "fr": {
        "Show in Enigma2 main menu": "Afficher dans le menu principal Enigma2",
        "Main menu setting saved": "Paramètre du menu principal enregistré. Redémarrez l'interface.",
        "Could not save setting": "Impossible d’enregistrer le paramètre"
    },
    "hu": {
        "Show in Enigma2 main menu": "Megjelenítés az Enigma2 főmenüben",
        "Main menu setting saved": "Főmenü beállítása mentve. Indítsa újra a GUI-t.",
        "Could not save setting": "A beállítás nem menthető"
    },
    "it": {
        "Show in Enigma2 main menu": "Mostra nel menu principale Enigma2",
        "Main menu setting saved": "Impostazione del menu principale salvata. Riavviare la GUI.",
        "Could not save setting": "Impossibile salvare l'impostazione"
    },
    "lt": {
        "Show in Enigma2 main menu": "Rodyti pagrindiniame Enigma2 meniu",
        "Main menu setting saved": "Pagrindinio meniu nustatymas išsaugotas. Paleiskite GUI iš naujo.",
        "Could not save setting": "Nepavyko išsaugoti nustatymo"
    },
    "nl": {
        "Show in Enigma2 main menu": "Tonen in het Enigma2-hoofdmenu",
        "Main menu setting saved": "Hoofdmenu-instelling opgeslagen. Herstart de GUI.",
        "Could not save setting": "Kan instelling niet opslaan"
    },
    "pl": {
        "Show in Enigma2 main menu": "Pokaż w menu głównym Enigma2",
        "Main menu setting saved": "Zapisano ustawienie menu głównego. Uruchom ponownie GUI.",
        "Could not save setting": "Nie udało się zapisać ustawienia"
    },
    "pt": {
        "Show in Enigma2 main menu": "Mostrar no menu principal do Enigma2",
        "Main menu setting saved": "Definição do menu principal guardada. Reinicie a interface.",
        "Could not save setting": "Não foi possível guardar a definição"
    },
    "ro": {
        "Show in Enigma2 main menu": "Afișează în meniul principal Enigma2",
        "Main menu setting saved": "Setarea meniului principal a fost salvată. Reporniți interfața.",
        "Could not save setting": "Setarea nu a putut fi salvată"
    },
    "ru": {
        "Show in Enigma2 main menu": "Показывать в главном меню Enigma2",
        "Main menu setting saved": "Настройка главного меню сохранена. Перезапустите GUI.",
        "Could not save setting": "Не удалось сохранить настройку"
    },
    "sk": {
        "Show in Enigma2 main menu": "Zobraziť v hlavnom menu Enigma2",
        "Main menu setting saved": "Nastavenie hlavného menu bolo uložené. Reštartujte GUI.",
        "Could not save setting": "Nastavenie sa nepodarilo uložiť"
    },
    "tr": {
        "Show in Enigma2 main menu": "Enigma2 ana menüsünde göster",
        "Main menu setting saved": "Ana menü ayarı kaydedildi. GUI'yi yeniden başlatın.",
        "Could not save setting": "Ayar kaydedilemedi"
    },
    "uk": {
        "Show in Enigma2 main menu": "Показувати в головному меню Enigma2",
        "Main menu setting saved": "Налаштування головного меню збережено. Перезапустіть GUI.",
        "Could not save setting": "Не вдалося зберегти налаштування"
    },
    "zh": {
        "Show in Enigma2 main menu": "在 Enigma2 主菜单中显示",
        "Main menu setting saved": "主菜单设置已保存。请重启图形界面。",
        "Could not save setting": "无法保存设置"
    }
}



_SAVER_TEXT = {
    "al": {
        "Screensaver after": "Kursyesi i ekranit pas",
        "Off": "Fikur",
        "Now playing radio": "Radioja po luan",
        "Artist": "Artisti",
        "Song": "Kënga",
        "Waiting for song information": "Në pritje të të dhënave të këngës",
        "Screensaver setting saved": "Cilësimi i kursyesit u ruajt"
    },
    "cs": {
        "Screensaver after": "Spořič obrazovky po",
        "Off": "Vypnuto",
        "Now playing radio": "Právě hraje rádio",
        "Artist": "Interpret",
        "Song": "Skladba",
        "Waiting for song information": "Čekám na údaje o skladbě",
        "Screensaver setting saved": "Nastavení spořiče uloženo"
    },
    "de": {
        "Screensaver after": "Bildschirmschoner nach",
        "Off": "Aus",
        "Now playing radio": "Radio läuft",
        "Artist": "Interpret",
        "Song": "Titel",
        "Waiting for song information": "Warte auf Titelinformationen",
        "Screensaver setting saved": "Bildschirmschoner gespeichert"
    },
    "el": {
        "Screensaver after": "Προφύλαξη οθόνης μετά",
        "Off": "Ανενεργό",
        "Now playing radio": "Παίζει ραδιόφωνο",
        "Artist": "Καλλιτέχνης",
        "Song": "Τραγούδι",
        "Waiting for song information": "Αναμονή στοιχείων τραγουδιού",
        "Screensaver setting saved": "Η ρύθμιση προφύλαξης αποθηκεύτηκε"
    },
    "en": {
        "Screensaver after": "Screensaver after",
        "Off": "Off",
        "Now playing radio": "Now playing radio",
        "Artist": "Artist",
        "Song": "Song",
        "Waiting for song information": "Waiting for song information",
        "Screensaver setting saved": "Screensaver setting saved"
    },
    "es": {
        "Screensaver after": "Salvapantallas después de",
        "Off": "Desactivado",
        "Now playing radio": "Radio en reproducción",
        "Artist": "Artista",
        "Song": "Canción",
        "Waiting for song information": "Esperando datos de la canción",
        "Screensaver setting saved": "Ajuste del salvapantallas guardado"
    },
    "et": {
        "Screensaver after": "Ekraanisäästja pärast",
        "Off": "Väljas",
        "Now playing radio": "Raadio mängib",
        "Artist": "Esitaja",
        "Song": "Lugu",
        "Waiting for song information": "Ootan loo teavet",
        "Screensaver setting saved": "Ekraanisäästja seadistus salvestatud"
    },
    "fa": {
        "Screensaver after": "محافظ صفحه پس از",
        "Off": "خاموش",
        "Now playing radio": "رادیو در حال پخش",
        "Artist": "هنرمند",
        "Song": "آهنگ",
        "Waiting for song information": "در انتظار اطلاعات آهنگ",
        "Screensaver setting saved": "تنظیم محافظ صفحه ذخیره شد"
    },
    "fr": {
        "Screensaver after": "Économiseur après",
        "Off": "Désactivé",
        "Now playing radio": "Radio en lecture",
        "Artist": "Artiste",
        "Song": "Titre",
        "Waiting for song information": "En attente des informations du titre",
        "Screensaver setting saved": "Économiseur enregistré"
    },
    "hu": {
        "Screensaver after": "Képernyővédő ennyi idő után",
        "Off": "Ki",
        "Now playing radio": "Rádió lejátszás",
        "Artist": "Előadó",
        "Song": "Dal",
        "Waiting for song information": "Várakozás a dal adataira",
        "Screensaver setting saved": "Képernyővédő beállítása mentve"
    },
    "it": {
        "Screensaver after": "Salvaschermo dopo",
        "Off": "Disattivato",
        "Now playing radio": "Radio in riproduzione",
        "Artist": "Artista",
        "Song": "Brano",
        "Waiting for song information": "In attesa dei dati del brano",
        "Screensaver setting saved": "Impostazione salvaschermo salvata"
    },
    "lt": {
        "Screensaver after": "Ekrano užsklanda po",
        "Off": "Išjungta",
        "Now playing radio": "Grojamas radijas",
        "Artist": "Atlikėjas",
        "Song": "Daina",
        "Waiting for song information": "Laukiama dainos duomenų",
        "Screensaver setting saved": "Užsklandos nustatymas išsaugotas"
    },
    "nl": {
        "Screensaver after": "Schermbeveiliging na",
        "Off": "Uit",
        "Now playing radio": "Radio speelt",
        "Artist": "Artiest",
        "Song": "Nummer",
        "Waiting for song information": "Wachten op nummerinformatie",
        "Screensaver setting saved": "Schermbeveiliging opgeslagen"
    },
    "pl": {
        "Screensaver after": "Wygaszacz ekranu po",
        "Off": "Wyłączony",
        "Now playing radio": "Radio odtwarza",
        "Artist": "Wykonawca",
        "Song": "Utwór",
        "Waiting for song information": "Oczekiwanie na informacje o utworze",
        "Screensaver setting saved": "Ustawienie wygaszacza zapisane"
    },
    "pt": {
        "Screensaver after": "Proteção de ecrã após",
        "Off": "Desligado",
        "Now playing radio": "Rádio em reprodução",
        "Artist": "Artista",
        "Song": "Música",
        "Waiting for song information": "A aguardar dados da música",
        "Screensaver setting saved": "Definição da proteção guardada"
    },
    "ro": {
        "Screensaver after": "Economizor de ecran după",
        "Off": "Dezactivat",
        "Now playing radio": "Radio în redare",
        "Artist": "Artist",
        "Song": "Melodie",
        "Waiting for song information": "Se așteaptă informații despre melodie",
        "Screensaver setting saved": "Setarea economizorului salvată"
    },
    "ru": {
        "Screensaver after": "Хранитель экрана через",
        "Off": "Выкл.",
        "Now playing radio": "Сейчас играет радио",
        "Artist": "Исполнитель",
        "Song": "Песня",
        "Waiting for song information": "Ожидание информации о песне",
        "Screensaver setting saved": "Настройка заставки сохранена"
    },
    "sk": {
        "Screensaver after": "Šetrič obrazovky po",
        "Off": "Vypnutý",
        "Now playing radio": "Práve hrá rádio",
        "Artist": "Interpret",
        "Song": "Skladba",
        "Waiting for song information": "Čakám na údaje o skladbe",
        "Screensaver setting saved": "Nastavenie šetriča uložené"
    },
    "tr": {
        "Screensaver after": "Ekran koruyucu süresi",
        "Off": "Kapalı",
        "Now playing radio": "Radyo çalıyor",
        "Artist": "Sanatçı",
        "Song": "Şarkı",
        "Waiting for song information": "Şarkı bilgisi bekleniyor",
        "Screensaver setting saved": "Ekran koruyucu ayarı kaydedildi"
    },
    "uk": {
        "Screensaver after": "Заставка через",
        "Off": "Вимкнено",
        "Now playing radio": "Зараз грає радіо",
        "Artist": "Виконавець",
        "Song": "Пісня",
        "Waiting for song information": "Очікування даних про пісню",
        "Screensaver setting saved": "Налаштування заставки збережено"
    },
    "zh": {
        "Screensaver after": "屏幕保护启动延时",
        "Off": "关闭",
        "Now playing radio": "电台正在播放",
        "Artist": "歌手",
        "Song": "歌曲",
        "Waiting for song information": "等待歌曲信息",
        "Screensaver setting saved": "屏幕保护设置已保存"
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
        _CACHE[code].update(_MAIN_MENU_TEXT[code])
        _CACHE[code].update(_SAVER_TEXT.get(code, {}))
    return _CACHE[code]


def t(text):
    return translations(language_code()).get(text, text)


def rtl():
    return language_code() == 'fa'


def group_label(group):
    """Translate display names while retaining catalogue group identities."""
    names = {'Slovensko': 'Slovakia', 'Čechy': 'Czechia', 'Custom': 'Custom'}
    return t(names[group]) if group in names else group
