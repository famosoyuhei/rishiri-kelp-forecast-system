#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Archive the nowcast_observation tab to CSV, then optionally delete it.

One-off maintenance for the accuracy workbook: the raw 10-minute nowcast
mesh tab grew to ~610k rows (~16M cells, ~80% of the workbook) and pushed
the spreadsheet to the Google Sheets cell limit. The daily summary tab
(nowcast_precip_daily_summary) is what accuracy analysis uses; the raw
tab is archived here before removal.

Safety:
  - The tab is streamed out in chunks to nowcast_observation.csv.gz and
    verified (row count from column A must match rows written, SHA-256 of
    the uncompressed CSV is printed).
  - The tab is deleted ONLY when CONFIRM_DELETE=1, and only after the
    archive file has been fully written and verified in the same run.
    Intended flow: run once with CONFIRM_DELETE unset (archive artifact
    is uploaded by the workflow), download and check the artifact, then
    run again with CONFIRM_DELETE=1.

Required environment variables:
  GOOGLE_SERVICE_ACCOUNT_JSON  Service-account key JSON
  RISHIRI_SPREADSHEET_ID       Target accuracy spreadsheet
Optional:
  CONFIRM_DELETE   Set to 1 to delete the tab after a verified archive.
"""

import csv
import gzip
import hashlib
import io
import json
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import quote

SPREADSHEET_ID = os.environ.get('RISHIRI_SPREADSHEET_ID', '')
CONFIRM_DELETE = os.environ.get('CONFIRM_DELETE', '') == '1'
TAB = 'nowcast_observation'
OUT_PATH = 'nowcast_observation.csv.gz'
SHEETS_API = 'https://sheets.googleapis.com/v4/spreadsheets'
CHUNK = 5000


def access_token() -> str:
    from google.oauth2 import service_account
    import google.auth.transport.requests

    raw = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    if not raw:
        raise RuntimeError('GOOGLE_SERVICE_ACCOUNT_JSON is not set')
    creds = service_account.Credentials.from_service_account_info(
        json.loads(raw),
        scopes=['https://www.googleapis.com/auth/spreadsheets'],
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def api(token: str, method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={'Authorization': f'Bearer {token}',
                 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='replace')[:500]
        raise RuntimeError(f'HTTP {e.code} for {method} {url}: {detail}') from e


def get_range(token: str, a1_range: str) -> list[list[str]]:
    url = (f"{SHEETS_API}/{SPREADSHEET_ID}/values/"
           f"{quote(a1_range, safe='')}")
    return api(token, 'GET', url).get('values', [])


def main() -> int:
    if not SPREADSHEET_ID:
        print('RISHIRI_SPREADSHEET_ID is not set', file=sys.stderr)
        return 2
    token = access_token()

    meta = api(token, 'GET', f'{SHEETS_API}/{SPREADSHEET_ID}')
    sheet = next(
        (s['properties'] for s in meta.get('sheets', [])
         if s['properties']['title'] == TAB),
        None,
    )
    if sheet is None:
        print(f'tab {TAB!r} not found — nothing to archive')
        return 0
    sheet_id = sheet['sheetId']

    # Count data rows via column A (upsert_key is the first column).
    col_a = get_range(token, f'{TAB}!A:A')
    data_rows = len(col_a)
    if data_rows < 2:
        print(f'tab {TAB!r} has no data rows — refusing to proceed')
        return 1
    print(json.dumps({'tab': TAB, 'data_rows_incl_header': data_rows}))

    sha = hashlib.sha256()
    written = 0
    first_keys, last_keys = [], []
    with gzip.open(OUT_PATH, 'wb') as gz:
        text = io.TextIOWrapper(gz, encoding='utf-8', newline='')
        writer = csv.writer(text)
        header_len = None
        start = 1
        while start <= data_rows:
            end = min(start + CHUNK - 1, data_rows)
            rows = get_range(token, f'{TAB}!A{start}:ZZ{end}')
            if header_len is None:
                header_len = len(rows[0]) if rows else 0
            for row in rows:
                padded = list(row) + [''] * (header_len - len(row))
                line = io.StringIO()
                csv.writer(line).writerow(padded)
                encoded = line.getvalue().encode('utf-8')
                sha.update(encoded)
                text.write(line.getvalue())
                key = padded[0] if padded else ''
                if written < 3:
                    first_keys.append(key)
                last_keys = (last_keys + [key])[-3:]
                written += 1
            print(json.dumps({'chunk': f'{start}-{end}', 'written': written}))
            start = end + 1
        text.flush()
        text.detach()

    print(json.dumps({'written_rows': written,
                      'expected_rows': data_rows,
                      'csv_sha256': sha.hexdigest(),
                      'first_keys': first_keys,
                      'last_keys': last_keys}))
    if written != data_rows:
        print('row count mismatch — archive NOT trusted, tab kept',
              file=sys.stderr)
        return 1

    if not CONFIRM_DELETE:
        print('archive written and verified; CONFIRM_DELETE not set, '
              'tab kept')
        return 0

    api(token, 'POST', f'{SHEETS_API}/{SPREADSHEET_ID}:batchUpdate',
        {'requests': [{'deleteSheet': {'sheetId': sheet_id}}]})
    print(json.dumps({'deleted_tab': TAB, 'sheet_id': sheet_id}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
