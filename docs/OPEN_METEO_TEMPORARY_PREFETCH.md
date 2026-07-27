# Open-Meteo Temporary Prefetch

This is a temporary mitigation for about one week while Open-Meteo may be
rate-limiting Render's outbound IP or usage pattern.

## Purpose

Move only the raw Open-Meteo fetch for LINE notifications away from Render:

```text
GitHub Actions -> Open-Meteo -> Upstash Redis -> Render -> existing LINE logic
```

GitHub Actions stores raw Open-Meteo JSON. It does not calculate foehn effects,
drying scores, drying judgments, wind-direction labels, or LINE text.

## Notification Prefetch Times

Existing schedules:

- Render LINE evening notification: 16:00 JST
- Render LINE morning notification: 01:30 JST
- GitHub Actions LINE fallback: 16:05 JST and 01:35 JST
- Forecast history snapshot: 16:20 JST

Prefetch workflow:

- `30 6 * * *` UTC = 15:30 JST primary, for the 16:00 evening notification
- `40 6 * * *` UTC = 15:40 JST backup (added after the 2026-07-27 incident
  below — GitHub Actions' `schedule` trigger is best-effort and can skip a
  slot; the backup run is a harmless no-op if the primary already succeeded)
- `0 16 * * *` UTC = 01:00 JST primary, for the 01:30 morning notification
- `10 16 * * *` UTC = 01:10 JST backup, same rationale

### 2026-07-27 incident: missed schedule slot

The 15:30 JST run for 2026-07-27 never fired at all (confirmed via
`gh run list` — no run exists for that trigger time). By 16:00 JST the most
recent valid prefetch entry was from the previous day's evening run
(>22h old), past the 12h stale-expiry window, so `load_prefetch()` returned a
miss for every affected spot. With `OPEN_METEO_PREFETCH_ONLY=true`, Render
did not fall back to a live fetch (by original design, to avoid re-triggering
a real 429) and sent the generic "could not fetch forecast" fallback text to
every subscriber whose spots were affected. No 429 or circuit-open event
actually occurred that day — the failure was caused entirely by the missing
upstream prefetch data, not by Open-Meteo rate-limiting.

Two fixes were applied:

1. The backup cron schedules above, so a single missed GitHub Actions slot
   doesn't leave a multi-hour gap.
2. `_get_simple_forecast_for_spot()` (`line_integration.py`) now only skips
   the live fallback on a `PREFETCH_ONLY` miss when
   `open_meteo_guard.is_circuit_open()` is actually true. A miss while the
   circuit is closed (Open-Meteo isn't currently blocking us) falls back to a
   live fetch instead of guaranteeing an empty notification.

## GitHub Secrets

Required:

- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`

Optional future overrides:

- `OPEN_METEO_BASE_URL`
- `OPEN_METEO_MARINE_BASE_URL`
- `OPEN_METEO_API_KEY`

The current free Open-Meteo API path does not require an API key.

## Open-Meteo Request

LINE notifications use the simplified LINE forecast path, not the full web app
forecast path.

Endpoint:

- `https://api.open-meteo.com/v1/forecast`

Hourly variables:

- `relative_humidity_2m`
- `wind_speed_10m`
- `wind_direction_10m`
- `precipitation`

Daily variables:

- `temperature_2m_max`
- `temperature_2m_min`
- `wind_speed_10m_max`
- `relative_humidity_2m_mean`
- `precipitation_sum`
- `precipitation_probability_max`

Other request parameters:

- `timezone=Asia/Tokyo`
- `forecast_days=7`
- no `models`
- no explicit unit overrides

Actually used by LINE:

- daily date
- daily precipitation sum
- daily precipitation probability max
- daily wind speed max as fallback
- daily max temperature
- hourly 04:00-16:00 humidity minimum
- hourly 04:00-16:00 wind-speed average
- hourly 06:00 and 13:00 wind direction display
- hourly 04:00-16:00 precipitation sum for history compatibility

The LINE simplified forecast currently does not use summit forecast, elevation,
marine SST, pressure, or the full web-app foehn correction.

## Redis Keys

Raw forecast:

```text
om:prefetch:v1:forecast:{cache_identity}
```

GitHub Actions 429 circuit:

```text
om:circuit:v1:github_actions
```

Render's existing P0 key remains unchanged:

```text
om:circuit:v1
```

## Stored Value

```json
{
  "schema_version": 1,
  "source": "github_actions_prefetch",
  "api_type": "forecast",
  "fetched_at": "UTC ISO-8601",
  "valid_until": "UTC ISO-8601",
  "request_fingerprint": "...",
  "data": {}
}
```

`data` is the raw Open-Meteo response JSON.

## Freshness

- Fresh use: fetched within 6 hours
- Stale emergency use: fetched within 12 hours
- Older than 12 hours: do not use as a normal notification forecast

If stale data is used, LINE text can include:

```text
現在、予報データ更新が一時停止しているため、直近に取得した予報を使用しています。
```

## Render Environment Variables

- `OPEN_METEO_PREFETCH_ENABLED=false` by default
- `OPEN_METEO_PREFETCH_ONLY=false` by default

For the temporary operation:

```text
OPEN_METEO_PREFETCH_ENABLED=true
OPEN_METEO_PREFETCH_ONLY=true
```

Meaning:

- `PREFETCH_ENABLED=true`: try Redis prefetch first
- `PREFETCH_ONLY=true`: if prefetch is missing or invalid AND the P0 circuit
  (`om:circuit:v1`) is currently open, do not fetch Open-Meteo directly from
  Render. If the circuit is closed, a miss still falls back to a live fetch
  (see the 2026-07-27 incident note above) — `PREFETCH_ONLY` only prevents a
  live call while Open-Meteo is actually blocking us, not on every miss.

## 429 Behavior

GitHub Actions:

- no retry on 429
- stop remaining spots in the same run
- keep existing good Redis prefetch entries
- log only safe metadata and `Retry-After`
- open `om:circuit:v1:github_actions`

Render:

- keeps the existing P0 circuit breaker
- does not share GitHub Actions' circuit key as a hard stop
- with `PREFETCH_ONLY=true`, only skips the direct Open-Meteo fallback on a
  miss while the P0 circuit is open; a miss with the circuit closed still
  fetches live (see 2026-07-27 incident note above)

## Foehn And Drying Logic

No domain logic is copied to GitHub Actions. Render still performs the existing
LINE simplified scoring and LINE text generation from the raw response.

The full web-app foehn correction remains in Render's `/api/forecast` path and
is outside this temporary LINE prefetch scope.

## Enable

1. Add GitHub secrets `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN`.
2. Push the workflow and script.
3. Run the workflow manually once only when ready, or wait for the schedule.
4. On Render, set:
   - `OPEN_METEO_PREFETCH_ENABLED=true`
   - `OPEN_METEO_PREFETCH_ONLY=true`
5. Keep `FOEHN_DIAGNOSTICS_ENABLED=false`.

## Disable / Rollback

Set on Render:

```text
OPEN_METEO_PREFETCH_ENABLED=false
OPEN_METEO_PREFETCH_ONLY=false
```

The existing P0 circuit breaker remains available independently.

## One-Week Observation

Observe only existing logs and workflow results:

- GitHub Actions success count and 429 count
- Redis prefetch hit/miss/stale/invalid logs on Render
- LINE notification sent/failed/skipped counts
- whether Render avoids direct Open-Meteo fetches when `PREFETCH_ONLY=true`
- whether stale data is ever used

## Customer API Decision

Consider Open-Meteo Customer API in August or September if any of these occur:

- GitHub Actions also receives repeated 429
- prefetch misses cause repeated notification gaps
- required request volume grows beyond free fair-use comfort
- Render dedicated IP or proxy is less reliable than a paid API endpoint

## Not Covered

This temporary workflow does not prefetch:

- `/api/forecast`
- `/api/analysis/field`
- forecast history for all 334 spots
- archive API
- marine analysis
- high-altitude/emagram analysis
