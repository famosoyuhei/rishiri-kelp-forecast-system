#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sync the Rishiri kelp forecast accuracy data to Google Sheets.

GitHub Actions version. Replaces the n8n workflows that copied the app's
read-only "sheets" APIs into the accuracy dashboard spreadsheet
(see docs/N8N_GOOGLE_SHEETS_ACCURACY.md in this repository).

Semantics mirror the n8n Google Sheets nodes:
  - keyed tabs use appendOrUpdate on their key column
    (raw_feedback / forecast_snapshot / amedas_observation /
     nowcast_precip_daily_summary on `upsert_key`,
     forecast_precip_accuracy_by_horizon on `summary_key`)
  - summary tabs and spot_master are fully rewritten (clear + append)

Every app endpoint returns {"columns": [...], "rows": [{...}]} and needs
no authentication. Sections are independent: a failure in one is logged,
the rest still run, and the process exits non-zero if any section failed.

Required environment variables:
  GOOGLE_SERVICE_ACCOUNT_JSON  Service-account key JSON (the spreadsheet
                               must be shared with its email as editor)
  RISHIRI_SPREADSHEET_ID       Target accuracy spreadsheet
Optional:
  APP_BASE          App base URL (default: the Render production app)
  DAYS              Accuracy window in days (default: 90)
  SYNC_NOWCAST_RAW  Set to 1 to also sync the raw 10-minute nowcast mesh
                    tab (nowcast_observation). Off by default: it grows by
                    ~24k rows/day and would hit Sheets cell limits.
"""

import json
import os
import sys
import time
import urllib.request
from urllib.parse import quote

APP_BASE = os.environ.get(
    'APP_BASE', 'https://rishiri-kelp-forecast-system.onrender.com'
).rstrip('/')
SPREADSHEET_ID = os.environ.get('RISHIRI_SPREADSHEET_ID', '')
DAYS = os.environ.get('DAYS', '90')
SYNC_NOWCAST_RAW = os.environ.get('SYNC_NOWCAST_RAW', '') == '1'
SHEETS_API = 'https://sheets.googleapis.com/v4/spreadsheets'

# (tab, mode, key_column, path) — mode: 'upsert' or 'rewrite'
SECTIONS = [
    ('raw_feedback', 'upsert', 'upsert_key',
     '/api/validation/accuracy/sheets?days={days}'),
    ('forecast_snapshot', 'upsert', 'upsert_key',
     '/api/forecast/snapshots/sheets?max_days_ahead=6'),
    ('amedas_observation', 'upsert', 'upsert_key',
     '/api/observations/amedas/sheets'),
    ('nowcast_precip_daily_summary', 'upsert', 'upsert_key',
     '/api/observations/nowcast/daily-summary/sheets'),
    ('forecast_precip_accuracy_by_horizon', 'upsert', 'summary_key',
     '/api/validation/forecast-precip/accuracy-by-horizon/sheets'),
    ('spot_master', 'rewrite', None,
     '/api/integration/spots/sheets'),
]
if SYNC_NOWCAST_RAW:
    SECTIONS.append(
        ('nowcast_observation', 'upsert', 'upsert_key',
         '/api/observations/nowcast/sheets')
    )

# summary endpoint: tables key -> sheet tab (all rewritten).
# The endpoint returns bare row lists (no columns wrapper), so columns are
# derived from the row keys. Only the API's own recommended_sheet_tabs are
# synced: extra tables (by_day_days_ahead, coverage_*, reliability_*) are
# intentionally excluded — each new tab costs ~26k cells of grid and the
# workbook is at the Sheets 2,000,000-cell limit (seen 2026-11-18).
SUMMARY_TABS = {
    'by_day': 'summary_by_day',
    'by_days_ahead': 'summary_by_days_ahead',
    'by_area': 'summary_by_area',
    'by_buraku': 'summary_by_buraku',
}
SUMMARY_PATH = '/api/validation/accuracy/sheets/summary?days={days}'


def fetch_json(path: str) -> dict:
    url = APP_BASE + path.format(days=DAYS)
    last_error = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=300) as resp:
                if resp.status != 200:
                    raise RuntimeError(f'{path} returned HTTP {resp.status}')
                return json.load(resp)
        except Exception as e:  # Render free tier may cold-start; retry once
            last_error = e
            if attempt == 0:
                time.sleep(5)
    raise RuntimeError(f'fetch failed for {path}: {last_error}')


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
        url,
        data=data,
        method=method,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='replace')[:500]
        raise RuntimeError(f'HTTP {e.code} for {method} {url}: {detail}') from e


def cell(value) -> str:
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def get_values(token: str, tab: str) -> list[list[str]]:
    url = f"{SHEETS_API}/{SPREADSHEET_ID}/values/{quote(tab, safe='')}"
    return api(token, 'GET', url).get('values', [])


def ensure_tabs(token: str, tabs: list[str]) -> None:
    """Create any missing tabs, one at a time.

    A failure here must not abort the whole run: tabs that already exist
    (e.g. created by the Apps Script dashboard setup) still sync fine, and
    a genuinely missing tab fails only its own section with a clear log.
    """
    meta = api(token, 'GET', f'{SHEETS_API}/{SPREADSHEET_ID}')
    existing = {s['properties']['title'] for s in meta.get('sheets', [])}
    for tab in tabs:
        if tab in existing:
            continue
        try:
            api(token, 'POST', f'{SHEETS_API}/{SPREADSHEET_ID}:batchUpdate',
                {'requests': [{'addSheet': {'properties': {'title': tab}}}]})
            print(json.dumps({'tab': tab, 'created': True}))
        except Exception as e:
            print(f'TAB CREATE FAILED {tab}: {e}', file=sys.stderr)


def append_rows(token: str, tab: str, values: list[list[str]]) -> None:
    url = (
        f"{SHEETS_API}/{SPREADSHEET_ID}/values/{quote(tab, safe='')}"
        ':append?valueInputOption=RAW&insertDataOption=INSERT_ROWS'
    )
    for i in range(0, len(values), 500):
        api(token, 'POST', url,
            {'majorDimension': 'ROWS', 'values': values[i:i + 500]})


def upsert(token: str, tab: str, key_col: str,
           columns: list[str], rows: list[dict]) -> dict:
    existing = get_values(token, tab)
    header = [str(h).strip() for h in existing[0]] if existing else []
    body = existing[1:] if existing else []
    if not header:
        header = list(columns)
    else:
        for col in columns:
            if col not in header:
                header.append(col)
    if key_col not in header:
        raise RuntimeError(f"Tab {tab!r} has no {key_col!r} column")
    key_idx = header.index(key_col)

    existing_by_key: dict[str, tuple[int, list[str]]] = {}
    for i, raw_row in enumerate(body):
        padded = list(raw_row) + [''] * (len(header) - len(raw_row))
        key = padded[key_idx] if key_idx < len(padded) else ''
        if key and key not in existing_by_key:
            existing_by_key[key] = (i + 2, padded)

    updates, inserts, unchanged = [], [], 0
    for row in rows:
        values = [cell(row.get(col)) for col in header]
        key = values[key_idx]
        if not key:
            continue
        if key in existing_by_key:
            row_number, current = existing_by_key[key]
            if current[:len(values)] != values:
                updates.append((row_number, values))
            else:
                unchanged += 1
        else:
            inserts.append(values)

    quoted = f"'{tab}'"
    value_ranges = []
    if not existing:
        value_ranges.append({'range': f'{quoted}!A1',
                             'majorDimension': 'ROWS', 'values': [header]})
    for row_number, values in updates:
        value_ranges.append({'range': f'{quoted}!A{row_number}',
                             'majorDimension': 'ROWS', 'values': [values]})
    for i in range(0, len(value_ranges), 500):
        api(token, 'POST', f'{SHEETS_API}/{SPREADSHEET_ID}/values:batchUpdate',
            {'valueInputOption': 'RAW', 'data': value_ranges[i:i + 500]})
    if inserts:
        append_rows(token, tab, inserts)
    return {'tab': tab, 'rows': len(rows), 'updated': len(updates),
            'inserted': len(inserts), 'unchanged': unchanged}


def rewrite(token: str, tab: str, columns: list[str],
            rows: list[dict]) -> dict:
    """Replace a tab's contents in place.

    Never clear-then-append: if the append is rejected (e.g. the workbook
    cell limit), a cleared tab would be left empty. Instead overwrite from
    A1 with values.update (no grid growth for same-size content), then
    clear only the tail rows the new content no longer covers.
    """
    values = [list(columns)] + [
        [cell(row.get(col)) for col in columns] for row in rows
    ]
    existing = get_values(token, tab)
    old_rows = len(existing)
    quoted = f"'{tab}'"
    for i in range(0, len(values), 500):
        chunk = values[i:i + 500]
        url = (f"{SHEETS_API}/{SPREADSHEET_ID}/values/"
               f"{quote(f'{tab}!A{i + 1}', safe='')}"
               '?valueInputOption=RAW')
        api(token, 'PUT', url, {'majorDimension': 'ROWS', 'values': chunk})
    if old_rows > len(values):
        tail = f'{tab}!A{len(values) + 1}:ZZ{old_rows}'
        url = (f"{SHEETS_API}/{SPREADSHEET_ID}/values/"
               f"{quote(tail, safe='')}:clear")
        api(token, 'POST', url)
    return {'tab': tab, 'rows': len(rows), 'rewritten': True}


def run_section(token: str, tab: str, mode: str, key_col: str | None,
                payload: dict) -> dict:
    columns = payload.get('columns') or []
    rows = payload.get('rows') or []
    if not columns:
        return {'tab': tab, 'rows': 0, 'skipped': 'no columns in payload'}
    if mode == 'upsert':
        if not rows:
            return {'tab': tab, 'rows': 0, 'skipped': 'no rows'}
        return upsert(token, tab, key_col, columns, rows)
    return rewrite(token, tab, columns, rows)


def report_grid_sizes(token: str) -> None:
    """Print each tab's grid size so cell-limit problems are diagnosable."""
    try:
        meta = api(token, 'GET', f'{SHEETS_API}/{SPREADSHEET_ID}')
        total = 0
        for s in meta.get('sheets', []):
            props = s.get('properties', {})
            grid = props.get('gridProperties', {})
            cells = grid.get('rowCount', 0) * grid.get('columnCount', 0)
            total += cells
            print(json.dumps({'grid': props.get('title'),
                              'rows': grid.get('rowCount'),
                              'cols': grid.get('columnCount'),
                              'cells': cells}))
        print(json.dumps({'grid_total_cells': total}))
    except Exception as e:
        print(f'GRID REPORT FAILED: {e}', file=sys.stderr)


def trim_tab(token: str, sheet_id: int, tab: str,
             keep_rows: int, keep_cols: int,
             cur_rows: int, cur_cols: int) -> dict:
    """Shrink a tab's grid to its data extent plus a small margin.

    Append-driven growth leaves grids far larger than the data (the
    values API reports only data rows), and every reserved cell counts
    against the workbook limit. Only ever shrinks; rows/columns beyond
    the kept extent hold no values by construction.
    """
    new_rows = min(cur_rows, keep_rows)
    new_cols = min(cur_cols, keep_cols)
    if new_rows == cur_rows and new_cols == cur_cols:
        return {'tab': tab, 'trimmed': False}
    api(token, 'POST', f'{SHEETS_API}/{SPREADSHEET_ID}:batchUpdate', {
        'requests': [{
            'updateSheetProperties': {
                'properties': {
                    'sheetId': sheet_id,
                    'gridProperties': {
                        'rowCount': new_rows,
                        'columnCount': new_cols,
                    },
                },
                'fields': 'gridProperties',
            },
        }],
    })
    return {'tab': tab, 'trimmed': True,
            'rows': [cur_rows, new_rows], 'cols': [cur_cols, new_cols]}


def trim_synced_tabs(token: str, tabs: list[str]) -> None:
    """Trim each synced tab's grid to its current data extent + margin."""
    try:
        meta = api(token, 'GET', f'{SHEETS_API}/{SPREADSHEET_ID}')
    except Exception as e:
        print(f'TRIM FAILED (metadata): {e}', file=sys.stderr)
        return
    by_title = {
        s['properties']['title']: s['properties']
        for s in meta.get('sheets', [])
    }
    for tab in tabs:
        props = by_title.get(tab)
        if not props:
            continue
        try:
            values = get_values(token, tab)
            data_rows = len(values)
            data_cols = max((len(r) for r in values), default=0)
            if data_rows == 0:
                continue
            grid = props.get('gridProperties', {})
            result = trim_tab(
                token, props['sheetId'], tab,
                keep_rows=data_rows + 50, keep_cols=data_cols + 2,
                cur_rows=grid.get('rowCount', 0),
                cur_cols=grid.get('columnCount', 0),
            )
            if result.get('trimmed'):
                print(json.dumps(result))
        except Exception as e:
            print(f'TRIM FAILED {tab}: {e}', file=sys.stderr)


def main() -> int:
    if not SPREADSHEET_ID:
        print('RISHIRI_SPREADSHEET_ID is not set', file=sys.stderr)
        return 2
    token = access_token()
    report_grid_sizes(token)
    all_tabs = [s[0] for s in SECTIONS] + list(SUMMARY_TABS.values())
    ensure_tabs(token, all_tabs)
    # Free reserved-but-empty grid cells before syncing, so appends in
    # this run have headroom under the workbook cell limit.
    trim_synced_tabs(token, all_tabs)

    failures = 0
    for tab, mode, key_col, path in SECTIONS:
        try:
            payload = fetch_json(path)
            result = run_section(token, tab, mode, key_col, payload)
            print(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            failures += 1
            print(f'SECTION FAILED {tab}: {e}', file=sys.stderr)

    try:
        summary = fetch_json(SUMMARY_PATH)
        tables = summary.get('tables') or {}
        for table_key, tab in SUMMARY_TABS.items():
            try:
                table_rows = tables.get(table_key) or []
                columns: list[str] = []
                for row in table_rows:
                    for col in row:
                        if col not in columns:
                            columns.append(col)
                payload = {'columns': columns, 'rows': table_rows}
                result = run_section(token, tab, 'rewrite', None, payload)
                print(json.dumps(result, ensure_ascii=False))
            except Exception as e:
                failures += 1
                print(f'SECTION FAILED {tab}: {e}', file=sys.stderr)
    except Exception as e:
        failures += 1
        print(f'SECTION FAILED summary: {e}', file=sys.stderr)

    trim_synced_tabs(token, all_tabs)

    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
