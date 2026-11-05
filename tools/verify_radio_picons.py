#!/usr/bin/env python3
"""Verify real country packages and unchanged-update behaviour in temporary storage."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from WarderRadio.picon_download import COUNTRIES, PiconSettings, PiconTask, install

parser = argparse.ArgumentParser()
parser.add_argument('--countries', nargs='+', choices=[c[0] for c in COUNTRIES], default=['SK', 'CZ'])
parser.add_argument('--style', choices=['black', 'white', 'transparent'], default='black')
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='warder-radio-picons-') as directory:
    settings = PiconSettings(directory)
    settings.location = str(Path(directory, 'picons'))
    settings.style, settings.countries = args.style, args.countries
    task = PiconTask()
    result = install(directory, settings, task)
    print(json.dumps({'countries': args.countries, 'style': args.style, 'first': result}, ensure_ascii=False), flush=True)
    if result['failed']:
        print(json.dumps(task.drain(), ensure_ascii=False), flush=True)
        raise SystemExit(1)
    assert result['added'] > 0, result
    repeated = install(directory, settings, PiconTask())
    assert not repeated['failed'] and not repeated['added'] and not repeated['updated'], repeated
    assert repeated['unchanged'] == result['added'], (result, repeated)
    print(json.dumps({'repeat': repeated}, ensure_ascii=False), flush=True)
