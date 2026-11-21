"""Block proven mismatched site/preplayer favicons from being used as radio logos.

Only the *exact* UUID + source URL combination is rejected. If the source
catalogue later advertises correct branded artwork the record is eligible
again. Do not synthesize replacements or disturb already saved originals.
"""

SOURCE_BRANDING_MISMATCH = {
    # News website logo "15-й РЕГИОН" is not Dorozhnoe/Road Radio 91.2.
    '18d1c523-1740-4b9c-8efe-60341d841733':
        'https://region15.ru/wp-content/themes/region15/svg/logo1.svg',
    # Website's generic play button is not Mineplay FM's station logo.
    'a5a8c2c4-a145-4064-a668-0a402a88290b':
        'https://radio.nedodev.ru/favicon.svg',
    # Digital news portal BBCL logo, not the separately branded Radio Bio Bio.
    'ef9a0e26-0ebe-47e7-888a-867065654776':
        'https://www.biobiochile.cl/assets/escritorio/bbcl-2020/img/bbcl-logo-2-dark.svg',
    # Three different music stations share the site-wide Dobreff favicon.
    '7fbabf72-3dd2-4d7e-8924-94bcdbb51530':
        'https://dobreff.com/images/radio/favicon.svg',
    '94543b27-7148-4328-83d6-27927a452965':
        'https://dobreff.com/images/radio/favicon.svg',
    '9a627ab5-735d-40e7-9f5a-89863d6d4910':
        'https://dobreff.com/images/radio/favicon.svg',
    # Four differently named streams share a generic HodlHarmony player icon.
    'b52c9597-95d7-4310-9a5e-6006920bd2b2':
        'https://www.hodlharmony.com/radio/favicon.svg',
    'bce0553a-5414-4eab-906f-b9c81cb40b0c':
        'https://www.hodlharmony.com/radio/favicon.svg',
    'f0d18892-adaf-460e-bda0-9194a5eb3d55':
        'https://www.hodlharmony.com/radio/favicon.svg',
    'fea0fb4b-cba0-419d-b1c2-a128bfa210a6':
        'https://www.hodlharmony.com/radio/favicon.svg',
}


def mismatched_source(row):
    """Return bad favicon URL only when UUID and original URL both match."""
    if not isinstance(row, dict):
        return None
    key = row.get('stationuuid')
    value = row.get('favicon')
    if not isinstance(key, str) or not isinstance(value, str):
        return None
    candidate = SOURCE_BRANDING_MISMATCH.get(key)
    if candidate is not None and candidate == value.strip():
        return candidate
    return None
