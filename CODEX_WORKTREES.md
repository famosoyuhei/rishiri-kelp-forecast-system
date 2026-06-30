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

## ワークツリー選択表

やりたいことからワークツリーを即判断するための早見表です。

| やりたいこと | 開くワークツリー |
| --- | --- |
| `start.py` / Flask API / デプロイ設定の修正 | `app-core` |
| 地図 UI / `kelp_drying_map.html` / PWA / `service-worker.js` の修正 | `frontend-map` |
| LINE Webhook / 通知 / `line_integration.py` の修正 | `line-ops` |
| 精度検証 / AMeDAS / 研究スクリプト | `research-archive` |
| Google Sheets 連携 / n8n ワークフロー / 精度分析レポート | `accuracy-analysis` |
| LP / マーケティング文言 / 画像素材 / QR コード | `marketing` |
| 複数領域にまたがる大規模変更 | フルワークツリー（デスクトップ） |

> **迷ったら**: タスクで最初に触るファイルがどこの sparse に含まれるかで判断してください。
> 作業中に別領域のファイルが必要になった場合は、そのワークツリーを別途開くか、
> フルワークツリーに切り替えてください。

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

## 標準作業フロー（Claude Code / Codex 共通）

すべての作業はこの8ステップで進めてください。
AIエージェントが別領域のファイルに誤って触れるリスクを防ぎます。

```
1. 現在のワークツリーを確認する
   git worktree list
   → 作業するワークツリーが「ワークツリー選択表」と一致しているか確認

2. README_WORKTREE.md と CLAUDE.md を確認する
   - 編集対象ファイルと編集禁止ファイルを把握する
   - 今回の作業に関係するルール（ミニルール A〜H / LINE ルール L1〜L9 等）を確認する

3. 対象ファイルだけを探索する
   - sparse-checkout の範囲外ファイルは開かない
   - Grep / Glob は対象ワークツリー内に限定する

4. 修正する
   - 編集禁止ファイルには触れない
   - 本番コード以外（ドキュメント・テスト）の変更は別コミットに分ける

5. 関連テストのみ実行する
   - そのワークツリーの README_WORKTREE.md に記載のテストだけを実行する
   - 全テストスイートは不要（スコープ外テストの失敗に引きずられない）

6. git diff を確認する
   git diff --name-only
   → 想定外のファイルが含まれていないかチェック
   → 本番コード（start.py / kelp_drying_map.html / line_integration.py）が
     意図せず変更されていないか確認

7. コミットする
   - ドキュメント変更と本番コード変更は分けてコミットする
   - メッセージ形式: `<type>: <summary>` （例: `fix:` / `feat:` / `docs:`）

8. 必要なら main にマージする
   - sparse ワークツリーのブランチ（codex/*）から PR を作成する
   - squash merge で main に取り込む
   - マージ後は README_WORKTREE.md のマージ前チェックリストを通過したか確認する
```

> **ショートカット**: ステップ1〜2 で「このタスクはどのワークツリーか？」に迷ったら
> 上の「ワークツリー選択表」に戻ってください。

## Refresh Commands

Run these from the full desktop worktree if a sparse definition needs to be inspected:

```powershell
git worktree list
git -C C:\Users\ichry\.codex-worktrees\rishiri_konbu_weather_tool\app-core sparse-checkout list
git -C C:\Users\ichry\.codex-worktrees\rishiri_konbu_weather_tool\frontend-map sparse-checkout list
git -C C:\Users\ichry\.codex-worktrees\rishiri_konbu_weather_tool\line-ops sparse-checkout list
git -C C:\Users\ichry\.codex-worktrees\rishiri_konbu_weather_tool\research-archive sparse-checkout list
```
