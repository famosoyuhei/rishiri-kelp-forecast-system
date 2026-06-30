# Codex Sparse Worktrees

This repository has several sparse worktrees under:

`C:\Users\ichry\.codex-worktrees\rishiri_konbu_weather_tool`

Use these instead of the full desktop worktree whenever possible to reduce
context and file-search noise.

## Worktrees

| Worktree | Branch | Use for |
| --- | --- | --- |
| `app-core` | `codex/app-core-sparse` | Flask app, production API, Render config, shared tests |
| `frontend-map` | `codex/frontend-map-sparse` | Map UI, PWA, notifications UI, dashboard/mobile pages, landing assets |
| `line-ops` | `codex/line-ops-sparse` | LINE webhook, rich menu, notification operations, LINE tests |
| `research-archive` | `codex/research-archive-sparse` | Forecast accuracy, AMeDAS, archive analysis, meteorological verification |
| `accuracy-analysis` | `codex/accuracy-analysis` | Existing accuracy/Sheets focused workspace |
| `marketing` | `codex/marketing` | Existing launch and marketing workspace |

## Default Choice

- Start in `app-core` for backend or production behavior changes.
- Start in `frontend-map` for `kelp_drying_map.html`, PWA, mobile, dashboard, or visual UI work.
- Start in `line-ops` for LINE notification, webhook, rich menu, and subscriber-flow work.
- Start in `research-archive` for historical weather analysis and forecast-accuracy investigations.
- Use the full desktop worktree only when a task genuinely spans app code, generated artifacts, photos, and archives.

## Sparse Definition Notes

### app-core: HTML/UI files excluded (2026-06-30)

The following files were removed from `app-core`'s sparse-checkout to keep it backend-only:

| Removed file | Reason |
| --- | --- |
| `kelp_drying_map.html` | 7,100-line UI file; irrelevant to backend API work. Managed by `frontend-map`. |
| `dashboard.html` | UI only. Managed by `frontend-map`. |
| `mobile_forecast_interface.html` | UI only. Managed by `frontend-map`. |
| `rishiri_island_lp.html` | Landing page. Managed by `marketing`. |
| `offline.html` | PWA fallback page. Managed by `frontend-map`. |
| `rishiri_wind_names.js` | Deprecated since v2.6.15; removed from all active sparse definitions. |
| `favicon.svg` | Icon asset; no backend dependency. |
| `static/img/logo.png` | Image asset; no backend dependency. |
| `static/fonts/NotoSansJP.ttf` | Font asset; no backend dependency. |

`app-core` retains `service-worker.js` and `manifest.json` as **read references** so that
backend engineers can verify SW version-bump requirements and manifest rule-D compliance
without switching worktrees.

## Refresh Commands

Run these from the full desktop worktree if a sparse definition needs to be inspected:

```powershell
git worktree list
git -C C:\Users\ichry\.codex-worktrees\rishiri_konbu_weather_tool\app-core sparse-checkout list
git -C C:\Users\ichry\.codex-worktrees\rishiri_konbu_weather_tool\frontend-map sparse-checkout list
git -C C:\Users\ichry\.codex-worktrees\rishiri_konbu_weather_tool\line-ops sparse-checkout list
git -C C:\Users\ichry\.codex-worktrees\rishiri_konbu_weather_tool\research-archive sparse-checkout list
```
