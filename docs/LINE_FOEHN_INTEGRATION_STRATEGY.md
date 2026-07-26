# LINE Foehn Integration Strategy

This plan keeps the temporary LINE prefetch operation stable while LINE
notifications are gradually moved toward the same foehn-aware drying judgment
used by the web forecast.

## Current State

- LINE notifications must continue during the temporary Open-Meteo 429
  mitigation.
- `OPEN_METEO_PREFETCH_ENABLED=true` and `OPEN_METEO_PREFETCH_ONLY=true` make
  LINE read GitHub Actions prefetched raw Open-Meteo data from Redis.
- LINE still uses the simplified LINE forecast path.
- The web app `/api/forecast` still owns the full foehn, terrain, fog, CAPE,
  SST, and drying-score logic.
- GitHub Actions must not implement domain weather logic. It only stores raw
  upstream data.

## Stage 1: Compare Without Changing Notifications

Goal: make LINE-vs-web differences visible without changing LINE text or
notification timing.

Implemented foundation:

- `line_web_forecast_compare.compare_line_and_web_forecast(line_day, web_day)`
  compares one LINE simplified day with one web forecast day or `daily_summary`.
- `line_web_forecast_compare.compare_line_and_web_forecasts(line_days, web_days)`
  compares all matching days.
- `line_web_forecast_compare.log_shadow_comparison(...)` emits only aggregate,
  safe JSON fields when explicitly enabled.
- It is pure and does not fetch Open-Meteo, call Render, read Redis, or send
  LINE messages.
- It captures:
  - score and suitability differences
  - whether the web path has foehn adjustment
  - whether LINE daily precipitation differs from its 04:00-16:00 precipitation
  - whether web precipitation differs from LINE 04:00-16:00 precipitation

Feature flag:

```text
LINE_WEB_FORECAST_SHADOW_COMPARE_ENABLED=false
```

This flag is off by default.  Turning it on must not fetch web forecasts by
itself; it only permits logging when a caller has already supplied both LINE
and web forecast outputs.

Next Stage 1 work:

- Wire the opt-in shadow comparison to an already available web-equivalent
  output source.
- Keep it disabled by default.
- Log only safe aggregate fields:
  - score delta
  - suitability changed
  - foehn present
  - precipitation-window mismatch
  - no coordinates, URLs, payloads, Redis values, or LINE user identifiers

## Stage 2: Extract Web Domain Logic

Goal: avoid duplicating foehn logic in LINE.

Target flow:

```text
raw Open-Meteo data
or prefetched raw Open-Meteo data
-> shared normalization
-> shared foehn correction
-> shared drying judgment
-> web response formatting / LINE text formatting
```

Rules:

- Do not copy foehn formulas into `line_integration.py`.
- Extract from `/api/forecast` toward shared pure helpers first.
- Keep normal `/api/forecast` responses unchanged while extracting.
- Add parity tests before changing LINE output.

## Stage 3: Expand Prefetch Inputs

Only after Stage 2 identifies the exact shared inputs, expand GitHub Actions
prefetch data.

Likely required data:

- Per registered spot:
  - forecast endpoint
  - the same hourly variables used by `/api/forecast`
  - the same daily variables used by `/api/forecast`
  - `timezone=Asia/Tokyo`
  - `forecast_days=7`
- Per registered spot elevation:
  - elevation endpoint or equivalent cached elevation source
- Summit reference:
  - forecast endpoint
  - summit coordinates used by web foehn logic
  - hourly `temperature_2m`
- Marine/SST:
  - marine endpoint
  - daily `sea_surface_temperature`

Do not prefetch all 334 spots for LINE unless the notification requirement
changes. Start with registered spots.

## Stage 4: Shadow Mode

Goal: compute web-equivalent LINE summaries without showing them to users yet.

Requirements:

- Disabled by default.
- No extra user-visible LINE text changes.
- Safe logs only.
- Stop on existing Open-Meteo circuit behavior.
- No automatic retry loops.

Decision gate:

- Several scheduled notification cycles show acceptable LINE-vs-web agreement,
  or the mismatches are understood and expected.

## Stage 5: Switch LINE Text To Web-Equivalent Values

Only after shadow mode is stable:

- Use the shared web-equivalent daily result for LINE score and suitability.
- Keep LINE text short.
- Add only the minimum useful foehn text, for example:
  - `Foehn correction: present`
  - corrected humidity if it is the value used for the score
- Replace the temporary simplified disclaimer.

## Rollback

At every stage, rollback must preserve current LINE continuity:

- Disable new shadow or web-equivalent LINE flags first.
- Keep temporary prefetch available while Render direct Open-Meteo access is
  uncertain.
- If needed, set:

```text
OPEN_METEO_PREFETCH_ENABLED=false
OPEN_METEO_PREFETCH_ONLY=false
```

This returns LINE to the pre-prefetch direct-fetch behavior, with the P0
Open-Meteo circuit breaker still available independently.
