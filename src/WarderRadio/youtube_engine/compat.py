"""Python 3 aliases required by the GPL-2.0 resolver and interpreter."""
from collections import ChainMap as compat_chain_map
from itertools import zip_longest as compat_zip_longest
from urllib.parse import parse_qs as compat_parse_qs
from urllib.request import Request as compat_Request, urlopen as compat_urlopen
from urllib.error import URLError as compat_URLError
compat_basestring = (str, bytes)
compat_str, compat_chr, compat_int, compat_map = str, chr, int, map
compat_integer_types = (int,)
compat_numeric_types = (int, float, complex)
SUBURI = "&suburi="
