#!/usr/bin/env python3
"""Download candidate daily control series from FRED into raw/public/ (network access; not used by model code).
Example: python code/fetch_fred.py VIXCLS DGS2 DFII10
"""
import hashlib
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / 'raw' / 'public'
URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id={}'

for sid in sys.argv[1:]:
    path = DEST / f'{sid}_fred.csv'
    if path.exists():
        print(sid, 'exists, not overwriting', path.name)
        continue
    data = urllib.request.urlopen(URL.format(sid), timeout=60).read()
    path.write_bytes(data)
    print(sid, datetime.now(timezone.utc).isoformat(timespec='minutes'), hashlib.sha256(data).hexdigest(),
          len(data.splitlines()) - 1, 'rows')
