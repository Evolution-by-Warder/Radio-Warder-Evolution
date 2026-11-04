"""Warder/PiconHub family header clock, independent of receiver locale packages.

Each label uses the current receiver's local time and Enigma2 interface language.
These fixed strings avoid system-wide locale changes, Babel, and extra dependencies.
Weekday names use Monday-first indexing. Month names are contextual date forms.
"""
import datetime
from .i18n import language_code

_NAMES = {
    "al": ("E hënë|E martë|E mërkurë|E enjte|E premte|E shtunë|E diel",
           "janar|shkurt|mars|prill|maj|qershor|korrik|gusht|shtator|tetor|nëntor|dhjetor"),
    "cs": ("Pondělí|Úterý|Středa|Čtvrtek|Pátek|Sobota|Neděle",
           "ledna|února|března|dubna|května|června|července|srpna|září|října|listopadu|prosince"),
    "de": ("Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag",
           "Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember"),
    "el": ("Δευτέρα|Τρίτη|Τετάρτη|Πέμπτη|Παρασκευή|Σάββατο|Κυριακή",
           "Ιανουαρίου|Φεβρουαρίου|Μαρτίου|Απριλίου|Μαΐου|Ιουνίου|Ιουλίου|Αυγούστου|Σεπτεμβρίου|Οκτωβρίου|Νοεμβρίου|Δεκεμβρίου"),
    "en": ("Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday",
           "January|February|March|April|May|June|July|August|September|October|November|December"),
    "es": ("Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo",
           "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre"),
    "et": ("Esmaspäev|Teisipäev|Kolmapäev|Neljapäev|Reede|Laupäev|Pühapäev",
           "jaanuar|veebruar|märts|aprill|mai|juuni|juuli|august|september|oktoober|november|detsember"),
    "fa": ("دوشنبه|سه‌شنبه|چهارشنبه|پنجشنبه|جمعه|شنبه|یکشنبه",
           "ژانویهٔ|فوریهٔ|مارس|آوریل|مهٔ|ژوئن|ژوئیهٔ|اوت|سپتامبر|اکتبر|نوامبر|دسامبر"),
    "fr": ("Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche",
           "janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre"),
    "hu": ("Hétfő|Kedd|Szerda|Csütörtök|Péntek|Szombat|Vasárnap",
           "január|február|március|április|május|június|július|augusztus|szeptember|október|november|december"),
    "it": ("Lunedì|Martedì|Mercoledì|Giovedì|Venerdì|Sabato|Domenica",
           "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"),
    "lt": ("Pirmadienis|Antradienis|Trečiadienis|Ketvirtadienis|Penktadienis|Šeštadienis|Sekmadienis",
           "sausio|vasario|kovo|balandžio|gegužės|birželio|liepos|rugpjūčio|rugsėjo|spalio|lapkričio|gruodžio"),
    "nl": ("Maandag|Dinsdag|Woensdag|Donderdag|Vrijdag|Zaterdag|Zondag",
           "januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december"),
    "pl": ("Poniedziałek|Wtorek|Środa|Czwartek|Piątek|Sobota|Niedziela",
           "stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia"),
    "pt": ("Segunda-feira|Terça-feira|Quarta-feira|Quinta-feira|Sexta-feira|Sábado|Domingo",
           "janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"),
    "ro": ("Luni|Marți|Miercuri|Joi|Vineri|Sâmbătă|Duminică",
           "ianuarie|februarie|martie|aprilie|mai|iunie|iulie|august|septembrie|octombrie|noiembrie|decembrie"),
    "ru": ("Понедельник|Вторник|Среда|Четверг|Пятница|Суббота|Воскресенье",
           "января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря"),
    "sk": ("Pondelok|Utorok|Streda|Štvrtok|Piatok|Sobota|Nedeľa",
           "januára|februára|marca|apríla|mája|júna|júla|augusta|septembra|októbra|novembra|decembra"),
    "tr": ("Pazartesi|Salı|Çarşamba|Perşembe|Cuma|Cumartesi|Pazar",
           "Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık"),
    "uk": ("Понеділок|Вівторок|Середа|Четвер|Пʼятниця|Субота|Неділя",
           "січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня"),
    "zh": ("星期一|星期二|星期三|星期四|星期五|星期六|星期日",
           "一月|二月|三月|四月|五月|六月|七月|八月|九月|十月|十一月|十二月"),
}
_NAMES = {code: (tuple(week.split("|")), tuple(month.split("|")))
          for code, (week, month) in _NAMES.items()}


def clock_text(now=None, language=None):
    """Return (weekday, full date, hours/minutes, colon+seconds), receiver local time."""
    if now is None:
        now = datetime.datetime.now()
    code = language_code(language)
    days, months = _NAMES.get(code, _NAMES["en"])
    day = days[now.weekday()]
    month = months[now.month - 1]
    if code == "zh":
        date = "%d年%d月%d日" % (now.year, now.month, now.day)
    elif code == "hu":
        date = "%d. %s %d." % (now.year, month, now.day)
    elif code in ("es", "pt"):
        date = "%d de %s de %d" % (now.day, month, now.year)
    elif code in ("sk", "cs", "de", "pl", "en"):
        date = "%d. %s %d" % (now.day, month, now.year)
    else:
        date = "%d %s %d" % (now.day, month, now.year)
    return day, date, now.strftime("%H:%M"), ":" + now.strftime("%S")
