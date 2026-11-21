"""Exactly verified radio broadcaster logo sources for offline bulk packaging only.

No network on import or on Enigma2 GUI. Source URLs are pinned by UUID,
station name, country, and broadcaster website/stream identity.
"""
from urllib.parse import urlsplit
from uuid import UUID

SK_SOURCE = {
    '7ee66666-7361-468c-ace4-1f7a357b58f6': {
        'name': 'Rádio Topoľčany',
        'homepage': 'radiotopolcany.sk',
        'profile': 'https://www.radia.sk/radia/topolcany',
        'logo': 'https://www.radia.sk/_radia/loga/coverflow/topolcany.png',
    },
    '913b7498-8e2d-420b-8c3b-dbacdf9597c4': {
        'name': 'Rádio Jazz',
        'homepage': 'radiojazz.sk',
        'profile': 'https://www.radia.sk/radia/jazz',
        'logo': 'https://cdn.radia.sk/_radia/loga/coverflow/jazz.png',
    },
    # This actual heading logo is linked from the verified Radia.sk profile.
    '8e94c1a0-d37c-4f3a-aa1a-0911a57fbc30': {
        'name': 'Party Radio',
        'homepage': 'partyradio.sk',
        'profile': 'https://www.radia.sk/radia/party',
        'logo': 'https://cdn.radia.sk/_radia/loga/nadpis/party.png?v=1',
    },
    '12e9aa8b-996e-4cf0-aace-3a8addf4dd57': {
        'name':'Radio Bela',
        'homepage':'radiobela.zanet.sk',
        'profile':'https://www.radia.sk/radia/bela',
        'logo':'https://www.radia.sk/_radia/loga/coverflow/bela.png',
    },
    'b141d7a8-81a2-4e96-8b3d-23e7938193fa': {
        'name':'Radio X Metal',
        'homepage':'stream.radiox.sk',
        'profile':'https://www.radia.sk/radia/x-metal',
        'logo':'https://cdn.radia.sk/_radia/loga/nadpis/x-metal.png?v=2',
    },
    '6102c39e-1f26-47d0-9223-e70987841a3d': {
        'name':'RTVS Litera256',
        'homepage':'live.slovakradio.sk',
        'homepage_path':'/Litera',
        'homepage_port':8000,
        'profile':'https://www.radia.sk/radia/litera',
        'logo':'https://www.radia.sk/_radia/loga/coverflow/litera.png',
    },
}
SAFE_IMAGE_HOSTS = frozenset(('www.radia.sk', 'cdn.radia.sk'))


def validated_source(row, source=SK_SOURCE):
    """Allow a known logo URL only for its exact, canonical UUID + brand."""
    if not isinstance(row, dict):
        return None
    uuid = row.get('stationuuid')
    record = source.get(uuid)
    if not record or row.get('countrycode') != 'SK':
        return None
    try:
        if uuid != str(UUID(uuid)):
            return None
    except (ValueError,TypeError,AttributeError):
        return None
    if row.get('name') != record['name']:
        return None
    try:
        homepage = urlsplit(row.get('homepage') or '')
        host = (homepage.hostname or '').lower().removeprefix('www.')
        logo = urlsplit(record['logo'])
        profile = urlsplit(record['profile'])
    except (AttributeError, TypeError, ValueError):
        return None
    if (homepage.scheme not in ('http', 'https') or
            host != record['homepage'] or
            (record.get('homepage_path') is not None and
             homepage.path != record['homepage_path']) or
            (record.get('homepage_port') is not None and
             homepage.port != record['homepage_port']) or
            logo.scheme != 'https' or
            logo.hostname not in SAFE_IMAGE_HOSTS or
            not logo.path.startswith(('/_radia/loga/coverflow/',
                                      '/_radia/loga/nadpis/')) or
            not logo.path.endswith('.png') or
            logo.query not in ('', 'v=1', 'v=2', 'v=4') or
            logo.fragment or logo.username or logo.password or
            profile.scheme != 'https' or profile.hostname != 'www.radia.sk' or
            not profile.path.startswith('/radia/')):
        return None
    return record



def verified_logo_url(row):
    match=validated_source(row)
    return match["logo"] if match is not None else None
