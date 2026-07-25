# Open-Meteo 429 P0 Guard

## Scope

This P0 change only prevents continued Open-Meteo traffic after a 429 in these
paths:

- LINE notifications
- `/api/forecast`
- `/api/analysis/field`
- daily forecast history snapshot

It does not implement full shared forecast caching, 49-point batch forecast
requests, single-flight, or stale-if-error.

## Circuit Breaker

Redis key:

`om:circuit:v1`

Value shape:

```json
{
  "opened_at": "UTC ISO-8601",
  "retry_after_at": "UTC ISO-8601",
  "reason": "429",
  "source": "line|forecast|field|history",
  "consecutive_429_count": 1
}
```

When the circuit is open, guarded paths do not send an Open-Meteo request and
fall through to their existing error or simplified failure handling.

`Retry-After` is parsed as either seconds or an HTTP date. A five-minute safety
buffer is added. If `Retry-After` is missing, fallback TTLs are:

- 1st consecutive 429: 30 minutes
- 2nd: 60 minutes
- 3rd: 2 hours
- 4th and later: 6 hours

The app never sends an automatic probe request. The next normal request after
the circuit expires is the next opportunity to close the circuit.

## Feature Flag

`OPEN_METEO_CIRCUIT_BREAKER_ENABLED`

Default: `true`.

Set to `false`, `0`, `no`, or `off` to bypass the P0 guard and return to the
previous Open-Meteo request behavior.

`FOEHN_DIAGNOSTICS_ENABLED` is unchanged.

## Logging

Structured logs include only route-level metadata:

- `source`
- `event`
- cache state
- HTTP status
- elapsed milliseconds
- retry-after time
- consecutive 429 count
- processed count
- remaining count

Logs must not include full URLs, coordinates, forecast payloads, Redis values,
tokens, or LINE user identifiers.

## Not Yet Migrated

The following Open-Meteo paths are intentionally outside this P0 migration:

- high-altitude contour/emagram analysis
- direct marine contour analysis
- archive API collection
- legacy or calibration analysis paths
- miscellaneous terrain comparison helpers

They should be migrated only after the P0 behavior is verified in production.
