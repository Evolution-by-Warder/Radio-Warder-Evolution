"""Isolated receiver-friendly progressive/HLS settings; no image config writes."""
from types import SimpleNamespace as NS
config = NS(plugins=NS(YouTube=NS(maxResolution=NS(value="38"),
    useDashMP4=NS(value=True), searchLanguage=NS(value="en"))))
