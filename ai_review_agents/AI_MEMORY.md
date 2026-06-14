# 🧠 AI社員 共有メモリー

> **使い方**: Claude CodeやCoworkでAI社員を動かした後、
> 発見した重要事項をこのファイルに追記してください。
> 次のセッションの冒頭で「AI_MEMORY.mdを読んでから作業してください」と
> 伝えるだけで、前回の続きから始められます。

---

## 📌 現在の既知問題（未解決）

| # | 重大度 | 担当社員 | 問題 | 発見日 | 状態 |
|---|--------|---------|------|--------|------|
| 1 | 🟡 MAJOR | 社員13 | `CORS(app, origins=[...])` にステージング環境URLがあれば追加が必要 | 2026-05-25 | 本番URL+localhostのみ設定済み。追加URLがあれば要対応 |
| 2 | 🟡 MAJOR | 社員9 | LINE `/api/line/status` エンドポイントに認証なし（誰でもLINE接続状況を確認可能） | 2026-05-25 | **✅修正済(2026-05-31)** `X-Admin-Secret` ヘッダー認証を追加。未設定時は開放（後方互換） |
| 3 | 🟡 MAJOR | 社員13 | `flask-limiter` のインメモリストレージ（Render再起動でリセット）。本番はRedis推奨 | 2026-05-25 | **✅修正済(2026-05-31)** Upstash REST URLから `rediss://` URI を自動導出してRedis化。未設定時は `memory://` にフォールバック |
| 4 | 🟡 MINOR | 社員12 | `_FIELD_CACHE_TTL` がインメモリ（Workerプロセス間でキャッシュ共有不可） | 2026-05-25 | **✅修正済(2026-05-31)** Upstash REST API でハイブリッドキャッシュ実装（Redis primary + インメモリ fallback） |
| 5 | 🔴 CRITICAL | 社員7/12 | `static/icons/icon-192x192.png` / `badge-72x72.png` 欠損。通知アイコンが表示されない | 2026-05-28 | **✅修正済(2026-05-28)** Pillowで192×192/72×72 PNG生成。kelp_drying_map.html 3箇所+SW統一 |
| 6 | 🟡 MAJOR | 社員5 | `dashboard.html:791` が廃止済み `/api/analysis/contours` を呼ぶ（410エラー） | 2026-05-28 | **✅修正済(2026-05-28)** `/api/analysis/field` に移行。ボタン刷新（等値線→分布図5種） |
| 7 | 🟡 MAJOR | 社員11 | `/api/forecast` URLに `shortwave_radiation` 未含有（`direct_radiation` 使用中、fieldと不整合） | 2026-05-28 | **✅修正済(2026-05-28)** hourlyに `shortwave_radiation` 追加。solar_radiation は SW優先/DR fallback |
| 8 | 🟡 MAJOR | 社員8 | 降水量レイヤー追加後、チャットボットに降水量レイヤーの説明が未追加 | 2026-05-28 | **✅修正済(2026-05-28)** PATTERNS contourにキーワード8個追加。respondContour()を全レイヤー説明に更新 |
| 9 | 🟡 MAJOR | 社員6 | scoreColor閾値（70/50/30点）が `_score_color()`（80/50点）と不一致 | 2026-05-28 | **✅修正済(2026-05-28)** kelp_drying_map.html 2671/2808行 → 80/50の2閾値に統一 |
| 10 | 🟡 MAJOR | 社員13 | `imageDiv.innerHTML` に `data.message` を直接inject（XSSリスク低いが原則違反） | 2026-05-28 | **✅修正済(2026-05-31)** `_esc(data.message)` に変更（ルールF準拠） |

---

## ✅ 解決済み問題

| # | 重大度 | 問題 | 解決日 | 修正コミット |
|---|--------|------|--------|------------|
| C-1 | 🔴 CRITICAL | `matplotlib` をサーバーサイドで使用（Render Free Planでメモリ超過リスク） | 2026-05-25 | `generate_contour_map()` 約500行を完全削除、`/api/analysis/contours` → HTTP 410 に変更 |
| C-2 | 🔴 CRITICAL | `app_icon.png` と `logo.png` のパス不一致（調査結果: 同一ファイルでMD5一致。誤検知） | 2026-05-25 | 対応不要と確認 |
| C-3 | 🔴 CRITICAL | `get_analysis_field()` のdispatchブロック欠落（`cache_key`・`target_date`未定義、if/elif全体なし） | 2026-05-25 | 変数割り当て＋if/elif/else分岐を完全復元 |
| M-1 | 🟡 MAJOR | `datetime.now()` をタイムゾーンなしで使用（UTC環境のRenderでJSTオフセットバグ） | 2026-05-25 | モジュール先頭に `JST = timezone(timedelta(hours=9))` 追加、全11箇所を `datetime.now(tz=JST)` に変換 |
| M-2 | 🟡 MAJOR | `CORS(app)` で全オリジン許可（本番環境でセキュリティリスク） | 2026-05-25 | `CORS(app, origins=["https://rishiri-kelp-forecast-system.onrender.com", "http://localhost:5000", "http://127.0.0.1:5000"])` に変更 |
| M-3 | 🟡 MAJOR | APIレート制限なし（`/api/forecast` が無制限→Open-Meteo連続呼び出しリスク） | 2026-05-25 | `flask-limiter` 導入、`/api/forecast` に30回/分、`/api/analysis/field` に20回/分の制限を追加 |
| M-4 | 🟡 MAJOR | `/add` エンドポイントでCSV Injection（改行・NULLバイトをCSVに書き込み可能） | 2026-05-25 | `_sanitize_csv_field()` 関数追加、town/district/burakuをサニタイズ |
| M-5 | 🟡 MAJOR | `/api/analysis/contours` の非推奨エンドポイントが旧コードのまま動作 | 2026-05-25 | matplotlibブランチ → HTTP 410 Gone レスポンスに差し替え |
| M-6 | 🟡 MAJOR | `manifest.json` に存在しないPNG画像を参照（`screenshots` セクション） | 2026-05-25 | `screenshots` セクションを丸ごと削除 |
| M-7 | 🟡 MAJOR | `manifest.json` のショートカットアイコンに存在しないPNGを参照 | 2026-05-25 | 全ショートカットアイコンを `/static/icons/icon.svg` に変更 |
| M-8 | 🟡 MAJOR | `line_integration.py` のLINE署名検証スキップ警告が `WARNING` レベル（見落としリスク） | 2026-05-25 | `logger.error()` に昇格し、Renderで必須設定を促すメッセージに変更 |
| M-9 | 🟡 MAJOR | `<canvas>` 要素にaria属性なし（アクセシビリティ違反） | 2026-05-25 | `emagramCanvas` と `forecastChart` に `role="img"` と `aria-label` を追加 |
| M-10 | 🟡 MAJOR | GitHub ActionsのCI（flake8）で `.venv` をスキャンして誤F821大量発生 | 2026-05-25 | `quality.yml` の `--extend-exclude` に `.venv` と `rishiri-kelp-forecast-system` を追加 |
| CI-1 | 🔴 CRITICAL | 7つのヘルパー関数が `start.py` から欠落（rebaseで消失）→ F821エラーでCI失敗 | 2026-05-25 | `_field_target_date` / `_fetch_open_meteo_multi` / `_extract_day_window` / `_safe_max` / `_safe_min` / `_safe_avg` / `_safe_sum` を完全復元 |

---

## 🏛️ 確定した設計判断（覆さないこと）

- **降水量閾値**: `precipitation == 0`（`< 1` は不可。0.5mm雨でも昆布干し不可）
- **降水ゲート**: `calculate_enhanced_drying_score()` 末尾に必ず最終ゲートを置く（`>=0.5mm → cap 8`, `>0mm → cap 30`）。局所リスク調整は呼び出し側で適用する
- **4補正の統一**: CAPE・霧・フェーン・SST は `/api/forecast` と `_compute_score_field` の両方で同じ関数/ロジックで計算すること。片方だけ0固定は不可
- **SST取得**: 島は直径20kmのため Marine API は島中心1点（45.1821N, 141.2421E）で代表。48格子点で個別取得は不要
- **時刻統一**: すべてJST（UTC+9）。`datetime.now()` ではなく `datetime.now(JST)` を使う
- **気温補正**: 削除済み（Open-Meteoが自動補正するため二重補正を避ける）
- **特別地点**: A_/R_ プレフィックスの3地点は削除禁止・記録禁止
- **4ファイル同期**: CSV/KML/JS/Records は常に同時更新。単独更新は不可

---

## 📊 レビュー実施履歴

| 日付 | モード | 担当社員 | 🔴CRITICAL | 🟡MAJOR | 🟢MINOR |
|------|--------|---------|-----------|---------|---------|
| 2026-05-25 | /full-review（13エージェント全員） | 社員1〜14 | 3件発見→**0件**（全修正） | 22件発見→**4件残**（低優先度のみ） | 47件検出（次バージョン対応） |
| 2026-05-25 | /quick-review（高速5項目） | 統括社員 | **0件** ✅ Go判定 | - | - |
| 2026-05-28 | /full-review（13エージェント全員） | 社員1〜13 | **2件**（通知アイコンPNG欠損）| **11件**（dashboard/SW/API/chat等） | 12件 → **全修正済(2026-05-28)** |
| 2026-05-31 | /full-review（17エージェント全員） | 社員1〜17 | **0件** ✅ | **2件**（manifest.json version / LINE L1違反）→ **全修正済(2026-05-31)** | 2件（scoreColor同期・SW命名）→ **全修正済(2026-05-31)** |

---

## 🗓️ 今週のスプリント状況

**リリース目標日**: 2026年5月31日（あと2日）

### 2026-05-29 完了
- [x] ~~お気に入り・Web通知の完全削除（v2.6.5）~~
- [x] ~~LINEリッチメニュー文字化け修正~~
- [x] ~~モバイルスクロール修正（v2.6.7）~~
- [x] ~~LINE予報ヒント・降水量行・友達追加誘導（v2.6.8）~~
- [x] ~~Upstash Redis設定確認~~
- [x] ~~CLAUDE.md / AI_MEMORY.md 更新（ドキュメントv2.3）~~
- [x] ~~UptimeRobotでRenderスリープ防止（monitor #803177862）~~
- [x] ~~`登録解除 呼び名` コマンド追加（v2.6.9）~~
- [x] ~~干場削除にLINE登録チェック追加・ブロック理由一括表示（v2.6.10〜11）~~

### 2026-05-28 完了
- [x] ~~二重リング49点グリッドの実装・微調整~~（完了）
- [x] ~~時刻選択UIのスコア時無効化~~（完了）
- [x] ~~降水量レイヤー実装（島内分布タブ）~~（完了）
- [x] ~~/full-review 実行 → CRITICAL 2件 + MAJOR 11件確認~~（完了）
- [x] ~~CRITICAL修正（PNG生成 + パス統一）~~（完了）
- [x] ~~MAJOR MA-1〜MA-5 修正（dashboard/shortwave/chatbot/HTTP207/scoreColor）~~（完了）
- [x] ~~整合性3大予防ルール → CLAUDE.md 追記 + check_consistency.py 新規作成~~（完了）
- [x] ~~MINOR 12件全修正 + CLAUDE.md ミニルール集A〜H追記~~（完了）

### 残タスク（5/31まで）
- [x] ~~/full-review（17エージェント）実行 → CRITICAL 0件、MAJOR 2件修正済み（2026-05-31）~~
- [ ] 漁師さんにURL＋RELEASE_GUIDE_FOR_FISHERMEN.mdを共有（5/31）
- [ ] MA-10残件（XSSリスク低優先度）は5/31後でOK
- [ ] kelp_drying_map.html 7,000行超過 → 次回大型機能追加時にJS分離

### 2026-05-31 完了
- [x] /full-review（17エージェント全員）実行
- [x] MAJOR #1修正: manifest.json version "2.6.12" → "2.6.15"
- [x] MAJOR #2修正: line_integration.py L664 L1ルール違反（干場ID直接入力誘導）→ Webアプリへの誘導に変更
- [x] MINOR #1修正: kelp_drying_map.html scoreColor JS→Python _score_color() に16進値同期
- [x] SW version v2-6-16 → v2-6-17 にバンプ（kelp_drying_map.html変更に伴う必須更新）
- [x] 降水量実測比較ループ実装（v2.6.15）: _auto_compare_precip_forecast(), /api/nowcast/precip

---

## 💬 セッションログ（新しい順）

### 2026-06-14（降水量比較ループの Redis 永続化 + 04:00-16:00 窓統一）

**実施内容**:

#### 背景確認
- 「干せません通知が続いている」→ Open-Meteo Archive API で6月上旬の実測降水量を確認
  - 6/6: 0mm、6/7: 0mm、6/8: 微量、6/9〜12: 0mm — 降雨は限定的
  - →「干せません」通知の原因は降水量ではなくスコア閾値の問題の可能性が高い
- 予報 vs 実測比較が機能していない根本原因: Render のエフェメラルファイルシステムがデプロイ毎にリセットされ `amedas_data/` と `forecast_history/` が消える

#### コミット 68e93f5: AMeDAS+ナウキャスト降水量をRedisに永続化
- `_obs_redis_get()` / `_obs_redis_set()`: AMEDAS・ナウキャスト用 Redis 汎用ヘルパー
  - key: `amedas:obs:{station_id}:{YYYYMMDD}`, TTL: 90日
- `_collect_amedas_from_openmeteo()`: Redis 優先 → ローカルファイル migration → API 取得 → Redis保存 の順
- `_auto_compare_precip_forecast()`: AMEDAS データ読み込みを Redis 優先に変更
- `_record_nowcast_snapshot()`: 全334干場のナウキャスト降水量を `nowcast:daily:{YYYYMMDD}` に保存
  - NX dedup キー `nowcast:snap_done:{YYYYMMDD}:{HHMM}` (1時間TTL) で重複防止
  - `_daily_amedas_collection()` (03:00 JST) と `_scheduled_line_notify()` から呼び出し
- `/api/collect_amedas?days=14` で June 1〜13 のバックフィルを実行済み

#### コミット b7847d8: 予報履歴の降水量を04:00-16:00積算に修正
- `_save_forecast_history()` に `precipitation_0416` フィールドを追加
  - `/api/forecast` の `hourly_details` から時刻4〜16のデータを積算
  - `precip_0416 = round(sum(h.get('precipitation', 0) or 0 for h in hourly_data[4:17]), 2)`
  - 旧 `precipitation` (24時間合計) も互換用に残す

#### コミット 6d816fa: 乾燥スコアの降水量判定を04:00-16:00積算に変更
- `/api/forecast` の各日スコア計算で `daily['precipitation_sum'][i]` → 時間別データから04:00-16:00のみ積算に変更
  ```python
  start_hour = i * 24 + 4
  end_hour   = start_hour + 13
  precipitation = round(sum(p for p in _ph[start_hour:end_hour] if p is not None), 2)
  ```
- **設計根拠**: 干場は砂利。前夜どんなに雨が降っても04:00-16:00が0mmなら「干せる」と判定すべき

#### コミット 3bf3920: forecast_history を Redis に永続化
- `_obs_redis_scan_keys(pattern)`: SCAN ページング対応の新ヘルパー（count=500、cursor=0まで繰り返し）
- `_save_forecast_history()`: Redis に `forecast:hist:{spot_name}:{target_YYYYMMDD}` として保存
  - 同一 `forecast_date` の重複登録を dedup チェックで防止
  - ローカルファイルは副（バックアップ）、Redis が主
- `_auto_compare_precip_forecast()`: 予報履歴読み込みを Redis SCAN 優先に変更
  - SCAN pattern: `forecast:hist:*:{date_str}` → 全干場を一括取得
  - `fc_precip` は `precipitation_0416` 優先（旧データは `precipitation` で代替）
  - ローカルファイル fallback も維持（開発環境向け）
- SW: v2-6-21 → v2-6-22

**設計確認**:
- `/api/forecast` の降水量は 04:00-16:00 積算のみ（`_compute_score_field` も `_extract_day_window()` で同様）→ 完全統一
- `forecast:hist:*` キーは今夜 16:00 通知から蓄積開始、翌日以降の比較で利用可能

---

### 2026-05-31（v2.6.15〜: 降水量実測比較ループ + フルレビュー修正）

**実施内容**:

#### v2.6.15: 降水量実測比較ループ実装
- `_auto_compare_precip_forecast(date_str, station_id='11151')`: 毎朝03:00（AMEDAS収集後）に自動実行
  - `amedas_data/amedas_11151_{date}.json` から04:00-16:00降水量を集計
  - `forecast_history/*/forecast_*_for_{date}.json` を全干場でスキャン
  - `hoshiba_records.csv` と照合して干し記録の有無を確認
  - `feedback_log.csv` に upsert（キー: date + spot_name + days_ahead）
- `FEEDBACK_COLUMNS` 拡張: `actual_precip_0416_mm`, `actual_rain_0416`, `precip_forecast_correct` 等を追加
- `/api/validation/accuracy` に `precip_forecast_accuracy` ブロック追加: `no_rain_precision_pct`, `missed_rain_cnt`, `false_alarm_cnt`
- `/api/collect_amedas` でも手動トリガー時に同期実行

#### v2.6.15: JMA降水ナウキャスト（hrpns）追加
- `GET /api/nowcast/precip`: 250mメッシュ、5分更新、利尻島全334干場対応
- z=10で2タイル（913,367）（914,367）のみ取得 → 全干場カバー
- PNG 4ビットインデックス形式を正確にデコード（実タイルで確認済み）
- キャッシュTTL=300秒、レート制限20/分
- `kelp_drying_map.html`: 「🛰 ナウキャスト（この干場）」行をAMEDASバーに追加
- SW: v2-6-15 → v2-6-16

#### フルレビュー（2026-05-31）修正 → v2.6.15パッチ
- **MAJOR修正1**: `manifest.json` version "2.6.12" → "2.6.15"（ルールD）
- **MAJOR修正2**: `line_integration.py` L664 L1ルール違反修正（「干場IDを直接入力」→ Webアプリ誘導）
- **MINOR修正**: `kelp_drying_map.html` scoreColor 16進値をPython `_score_color()` に同期（ルール1）
  - `#16a34a → #1f9d55`（緑）、`#ca8a04 → #c9a500`（アンバー）、`#dc2626 → #d64545`（赤）
- SW: v2-6-16 → v2-6-17（kelp_drying_map.html変更に伴う必須バンプ）

#### v2.6.15 継続修正（2026-05-31 セッション2）— 全残件完了
- **伝統風名廃止**: `rishiri_wind_names.js` 物理削除。`/rishiri_wind_names.js` ルートを HTTP 410 Gone に変更
- **windDisplay() 統合**: `_WIND_DIR_16`（16方位英略語）+ `_WIND_ARROWS`（8方向矢印）→ `windDisplay(deg)` で `"↙ NE"` 形式に統一
  - kelp_drying_map.html 冒頭の旧 `RISHIRI_WIND_NAMES`/`getRishiriWindName()`/`getWindArrow()` 等 ~80行を削除
  - 日次サマリーカード・時間別テーブル共に `windDisplay()` に統一
- **#10 XSS修正**: `imageDiv.innerHTML` 内の `data.message` → `_esc(data.message)` に変更
- **#2 `/api/line/status` 認証追加**: `LINE_ADMIN_NOTIFY_SECRET` が設定されている場合、`X-Admin-Secret` ヘッダー必須。不一致で HTTP 401
- **#3 flask-limiter Redis化**: `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` から `rediss://` URI を自動導出。未設定時は `'memory://'` にフォールバック
- **#4 `_field_cache_get/set` Redis化**: Upstash REST API を使ったハイブリッドキャッシュ実装
  - `_fc_redis_get()` / `_fc_redis_set()`: REST GET/POST で JSON を EX TTL 付きで読み書き
  - `_field_cache_get()`: Redis primary → インメモリ fallback（同一Worker内の高速再読み用）
  - `_field_cache_set()`: Redis + インメモリに同時書き込み（best-effort）
- **CLAUDE.md 更新**: Section 4「利尻島伝統風名システム」→「風向表示システム（v2.6.15〜）」
- **SW**: v2-6-18 → v2-6-19（start.py + kelp_drying_map.html 変更に伴う必須バンプ）
- **PROJECT_STRUCTURE.md / README.md**: `rishiri_wind_names.js` のエントリを削除

**既知の問題（全て解決済み）**: なし

**設計確認**:
- 実測データ収集の「使命」: 毎日04:00-16:00の実測降水量 → 予報評価 → 干し記録照合 → 手がかり蓄積 ✅
- 1kmメッシュ降水短時間予報（JMA HRPNS）は「機能重複」のため今は実装不要と確認 ✅

---

### 2026-05-29（v2.6.9〜v2.6.11: 登録解除コマンド・削除ブロック改善）

**実施内容**:

#### v2.6.9: `登録解除 呼び名` コマンド追加（コミット 5a8afa2）
- 「干場削除」はWebアプリの物理削除と混同するため「登録解除」に命名
- `parse_command`: `登録解除` / `登録解除 呼び名` を `remove_spot` コマンドにマッピング
- `handle_remove_spot()`: 呼び名 or spot_id で検索し spot_nicknames + spots から削除
- `handle_list_spots()`: 末尾に「個別解除: 登録解除 呼び名」ヒントを追加
- `_HELP_TEXT`: 「干場一覧」「登録解除 呼び名」を追記
- `handle_register_spot_nickname()`: 登録完了メッセージに undo hint（`登録解除 {nickname}`）を追記

#### v2.6.10: LINE登録済み干場の削除ブロック（コミット 0b18158 / d9c196a）
- `delete_spot()` の旧2（お気に入り）・旧3（Web Push通知）を整理
- LINE購読チェック追加: Upstash Redis から `load_subscriptions()` を呼び出し、
  `spots` or `spot_nicknames.values()` に対象干場があれば 403 を返す
- エラーメッセージは「なぜ削除できないか」のみ。登録者特定・解除依頼の文言は不採用

#### v2.6.11: 削除ブロック理由の一括表示（コミット 72b666f）
- 早期リターンをやめ `block_reasons = []` に全理由を収集してから一括 403 を返す
- 記録あり＋LINE登録ありの両該当時も一度のメッセージで全理由を表示

**干場削除の現行条件（3条件）**:
1. 乾燥記録がない（`hoshiba_records.csv`）
2. LINE通知登録ユーザーがいない（Upstash Redis）
3. 同時編集ロックがかかっていない（5分、`edit_locks/`）

**UptimeRobot設定（monitor #803177862）**:
- `https://rishiri-kelp-forecast-system.onrender.com/health` を5分おきにping
- Renderフリープランのスリープ→LINEのreplyToken失効問題を解消

---

### 2026-05-29（v2.6.5〜v2.6.8: LINE一本化・モバイル修正・3機能追加）

**実施内容**:

#### v2.6.5: お気に入り・Web通知を完全削除（コミット ae613cb）
- `favorites` 変数・favoritesPanel・favoritesButton・Web Push Notification 関連を kelp_drying_map.html から全除去
- LINEリッチメニュー文字化け修正（NotoSansJP Black weight + stroke）
- SW v2-6-4 → v2-6-5

#### v2.6.7: モバイルスクロール修正（コミット ba7b644）
- 「7日間予報を表示」「LINE通知」ボタンを押してもパネルが見えなかった問題を修正
- 根本原因: モバイルのflex-direction:columnレイアウトではパネルが地図の下（画面外）に配置される
- 修正: `selectSpot()` に `panel.scrollIntoView({ behavior:'smooth', block:'start' })` を追加（768px以下のみ）
- `openLineRegistration()` も同様のスクロール処理を追加し、nickInput.focus() を350ms遅延実行
- SW v2-6-6 → v2-6-7

#### v2.6.8: LINE予報ヒント・降水量行・友達追加誘導（コミット 58c4814）
**Q1: LINE予報に追加干場ヒント** (`line_integration.py`)
- 新定数 `_ADD_SPOT_HINT = '📍 他の干場も追加したい場合はリッチメニュー「干場登録」からどうぞ。'`
- `handle_today()`, `handle_tomorrow()`, `handle_weekly()` の応答末尾に追加
- `handle_record_start()` にも「他の干場を追加したい場合は〜」ヒントを追加

**Q2: 一般タブ降水量行** (`kelp_drying_map.html`)
- `generateHourlyDetails()` の一般向けカテゴリ末尾に1時間刻み降水量行を追加
- 配色: 0mm=グレー / 0mm超=水色 / ≥1mm=濃青太字 / ≥5mm=赤背景太字
- データは `hour.precipitation ?? 0` で既存の hourly_details から取得（追加API不要）

**Q3: LINE友達追加誘導** (`kelp_drying_map.html`)
- `lineRegisterBtnWrap` の先頭に緑枠ボックスを追加
  - 内容: 「まずLINEで友達追加が必要です」＋「利尻昆布干場予報を友達追加する →」リンク
  - LINE OA: `@766cfpki` / URL: `https://line.me/R/ti/p/%40766cfpki`
- SWバージョン: v2-6-7 → v2-6-8

**Upstash Redis確認**:
- Render環境変数 `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` 設定済みを確認
- `load_subscriptions()` はUpstash優先、失敗時にローカルJSONフォールバック
- `save_subscriptions()` も同様の優先順位
- Redisキー: `line_subscriptions`
- **注意**: Renderの無料プランのファイルシステムはデプロイ毎にリセットされるため、ローカルJSONフォールバックにデータが入った状態でデプロイすると消える。Upstashに書かれたデータは永続

**既知の問題（引き続き未解決）**:
- 問題#2: `/api/line/status` に認証なし（誰でも確認可能）
- 問題#3: flask-limiterのインメモリストレージ（Render再起動でリセット）
- 問題#10: imageDiv.innerHTML に data.message 直接inject（低優先度）

**CLAUDE.md更新内容**:
- バージョン: v2.6.0 → v2.6.8 (2026年5月29日)
- kelp_drying_map.html 行数: 6,235 → 約7,100行（7,000行超過のため次回大型機能追加時にJS分離）
- Section 6: Web通知 → LINE通知に完全書き換え
- ドキュメントバージョン: 2.2 → 2.3
- v2.6.8 / v2.6.2〜v2.6.7 のchangelogエントリを追加

---

### 2026-05-28（島内分布グリッド: 二重リング + 利尻山頂）
**実施内容**: `_build_rishiri_grid()` を適応型48点リングから固定49点（山頂+二重リング）に刷新。

**変更内容**:
- 旧: CSV学習型適応リング 48点（重心45.1757N, 141.2222Eを中心に干場距離中央値で半径を調整）
- 新: 固定設計 49点
  - 利尻山頂 1点: (45.1800N, 141.2392E) `label='利尻山頂'`
  - 内リング 24点: r=7km, 方位 0°/15°/30°/.../345°, `label='内北1'`〜`'内北西3'`
  - 外リング 24点: r=8km, 方位 7.5°/22.5°/.../352.5°（内リングと7.5°千鳥）, `label='外北1'`〜`'外北西3'`

**設計根拠**:
- 利尻島の干場は沿岸 r=6〜9km 帯に分布（CSV測定: 平均7.53km）
- 7km/8kmの二重リングは実際の干場密集帯を網羅しつつ重複を最小化
- 山頂点を追加することで島全体の気象支配点（標高1,721m）のスコアを可視化
- 千鳥配置によりどの方位でも1km未満の空間分解能を確保

**ラベル規則** (8方位 × 3サブ = 24点/リング):
- 内リング: `内{8方位名}{1-3}`（例: 内北1, 内北東2, 内西3）
- 外リング: `外{8方位名}{1-3}`（例: 外北1, 外南東3）

**API検証結果** (`/api/analysis/field?type=score&day=0`):
- `points.Count = 49` ✅
- `points[0].name = '利尻山頂'` ✅
- `points[1].name = '内北1', bearing=0` ✅
- `points[25].name = '外北1', bearing=7.5` ✅（千鳥確認）
- `points[48].name = '外北西3', bearing=352.5` ✅

**次回やること**: 5/31リリース前の最終確認と漁師さんへの共有準備

---

### 2026-05-28（ローカルリスク補正の完全統一）
**実施内容**: `/api/forecast` と `/api/analysis/field` の4補正を完全一致させた（`d20727d`）。

**修正した不整合**:
| 補正 | /api/forecast | _compute_score_field（修正前） | 修正後 |
|---|---|---|---|
| CAPE | assess_cape_risk() | **0固定** | 同じ関数 |
| フェーン | 山頂方位角+angle_diff>150° | **0固定** | 同じ計算 |
| SST | Marine API取得 | **0固定** | 島中心で1回取得→共通適用 |
| 霧 | fog_risk集計 | dewpoint降下法 | 変更なし（同等） |

**実装の核心**:
- `hourly_vars` に `'cape'`, `'wind_direction_10m'` を追加
- ループ前に SST を島中心（45.1821N, 141.2421E）で1回取得（Marine API節約）
- フェーン計算: 格子点→利尻山頂の方位角 + `(wind_dir+180)%360` との角度差 > 150° + 風速 > 3m/s
- 適用順序も /api/forecast に準拠（CAPE → 霧 → フェーン+SST）

**検証結果**:
- `precip=1.7mm` → gate(8) → fog(-10)→0 → foehn(+8) → **val=8** ✓
- `precip=0mm` → 補正なし → **val=17** ✓
- `precip=1.8mm` → gate(8) → fog(-10)→0 → foehn 0 → **val=0** ✓

**次回やること**: 5/31リリース前の最終確認、漁師さんへの共有準備

---

### 2026-05-28（スコア不整合バグの根本修正）
**実施内容**: 島内分布タブと部落ランキングのスコアが大きく食い違う問題を調査・修正・コミット（`cdd8849`）。

**発見した根本原因**:
`calculate_enhanced_drying_score()` が降水量の「加点除外」しか行っておらず、**気温・風速・日射の積み上げ点が雨天でも自由に累積**していた（最大~45点）。
- `/api/forecast` は24時間合計降水量 + デフォルトモデル(ECMWF) で計算 → 0〜7点
- `/api/analysis/field` は04-16 JST窓降水量 + JMA seamlessモデル で計算 → 40〜48点
- 2つのコードパスの「降水ペナルティなし」問題が重複して見かけ上の大差を生んでいた

**修正内容** (`start.py` L1218-1226):
```python
# --- 最終降水ゲート（実測根拠による強制圧縮） ---
# 実測21件: 0.5mm以上は全件乾燥失敗 → 最大8点に強制圧縮（「不可」帯）
# 0〜0.5mm未満（微量）: 最大30点に圧縮（「要注意」帯）
if precipitation >= 0.5:
    score = min(score, 8)
elif precipitation > 0:
    score = min(score, 30)
return max(0, min(100, score))
```

**検証結果**:
- `precip=1.7mm → value=0`（局所リスク調整-10後にclamp）✅ （修正前: 40台）
- 島内全48格子点が `value=0` でランキングと整合 ✅
- `/api/forecast` との視覚的一致を確認 ✅

**設計判断の更新**:
- `calculate_enhanced_drying_score()` の末尾に必ず降水ゲートを置くこと
- 局所リスク調整（fog_penalty等）は呼び出し側で適用するため、ゲートはその前（=基礎スコア）に働く
- 2つのAPIパスが完全に同一スコア関数を使うようになったが、モデル/窓の差は残存（許容範囲）

**次回やること**: 5/31リリース前の残MAJOR対応、漁師さんへの共有準備

---

### 2026-05-28（ベンチマーク推奨機能の実装 — Feature A/B/C）
**実施内容**: グローバルベンチマーク結果に基づく3機能を実装・コミット（`77d47e0`）。

**Feature A: 自然言語サマリーカード（Captain's Brief方式）**
- `generateDailySummary()` + `summaryCardHTML()` を実装
- hourly_detailsから最長連続条件窓（降水0mm + 湿度≤94% + 風速≥2.0m/s）を検出
- 窓終了後リスクブロック: 実降水 > PoP≥60% > PoP≥40% > CAPE≥1000/500 — 事実ベース警告
- 各予報日カードの先頭にカード形式で自動挿入

**Feature B: 全島部落ランキング**
- `loadIslandRanking()`: hoshibaSpotsを部落でグループ化し中心点を選択、~32部落を並列fetch
- スコアを/100表示（/10ではなく）、閾値70/50/30でカラーリング
- 悪天候時のタイブレーカー: 条件窓の長さで二次ソート
- 30分TTL localStorageキャッシュ + 🔄更新ボタン
- `start.py`: `/api/forecast` レート制限 30→60 回/分（並列fetch対応）

**Feature C: 島内分布タブ完成**
- スコアマーカー: `L.circleMarker` → `L.marker` + `L.divIcon`（スコア数値入り円、20/24/28px）
- `_dimSpotMarkers()` / `_restoreSpotMarkers()`: タブ活性中は334干場マーカーを12%に減光
- `field-tooltip` CSSを追加（未定義クラスだった）
- バックエンド(`_compute_score_field`等)は既実装済みを確認済み

**確認済み動作**:
- 48格子点スコアが地図上に数値付きで表示 ✅
- タブ離脱/復帰で干場マーカーの透明度が正確に切り替わる（0.8↔0.12）✅
- field-tooltipが適切なダーク背景で表示 ✅

**次回やること**: 5/31リリース前の残MAJOR対応、または漁師さんへの共有準備

---

### 2026-05-28（グローバルベンチマーク実施）
**実施内容**: `/benchmark-review` スキルを初回実行。世界15本の漁業・沿岸・農業向け専門気象アプリを調査し8軸比較マトリクスを作成。

**結果サマリー**（詳細は `ai_review_agents/BENCHMARK_REPORT_20260528.md`）:
- 本システム現状スコア: **33/40**（PredictWind 30, Windy Marine 29, Meteoblue 29）
- 「漁業特化専門アプリ」カテゴリで**世界最高水準**と評価
- 強み軸: UX(5/5)・精度(5/5)・地域性(5/5)・通知(5/5)
- 改善軸: ビジュアル(3/5)・不確実性(2/5)

**重要発見: WINDY_RESEARCH.mdのロードマップ記述は古い**:
以下が v2.6.2 ですでに実装済みであることを確認:
- CAPE指数（W10）→ `assess_cape_risk()` 実装済み・スコア反映済み
- 降水確率PoP（W11）→ `precipitation_probability_max` 取得・スコア反映済み
- 海水温SST霧リスク（W6）→ `assess_sst_fog_risk()` 実装済み
- ソルナー理論（W9）→ `calculate_solunar_score()` 実装済み
- 霧リスクスコア（CLAUDE.md「未実装」）→ 露点降下量による fog_risk 判定実装済み

**ロードマップへの新規追加推奨**:
1. 「今日の作業サマリー」自然言語出力（Buoyweather Captain's Brief方式）
2. 「最適2時間窓」自動計算（Meteoblue Agro Spraying Window方式）
3. 日別予報信頼度インジケーター★表示（PredictWind方式の簡易版・極小コスト）
4. 干場間「今日のベスト干場」ランキング（Passage Weather概念の応用）

**次回やること**: WINDY_RESEARCH.mdとCLAUDE.mdの「未実装」記述を修正。ビジュアル向上（島内分布タブ）を優先着手。

---

### 2026-05-25（フルレビュー実施 + CRITICAL全修正 + v2.6.2デプロイ）
**実施内容**: Claude Codeで `/full-review`（13エージェント）を初回実行し、発見した全CRITICALを当日中に修正・デプロイ。

**レビュー結果**:
- 🔴 CRITICAL 3件 → 全修正（matplotlib削除 / dispatchブロック修復 / CI F821修復）
- 🟡 MAJOR 22件 → 18件修正、4件残（低優先度 → v2.7.0以降）
- 🟢 MINOR 47件 → 次バージョン対応

**主な修正内容**:
1. **matplotlib完全削除** (`generate_contour_map()` 約500行削除、requirements.txtから除去)
2. **datetime.now() → JST統一** (全11箇所、モジュール先頭に `JST = timezone(timedelta(hours=9))`)
3. **CORS本番制限** (`origins=[本番URL, localhost:5000, 127.0.0.1:5000]`)
4. **APIレート制限追加** (flask-limiter: /api/forecast 30/min, /api/analysis/field 20/min)
5. **CSV Injection対策** (`_sanitize_csv_field()` 追加)
6. **非推奨API → HTTP 410** (`/api/analysis/contours` matplotlibブランチ)
7. **manifest.json修正** (存在しないPNG削除、SVGに統一)
8. **LINE署名警告 → ERROR昇格**
9. **canvasアクセシビリティ** (aria-label追加)
10. **7つのヘルパー関数復元** (rebaseで消失: `_field_target_date`など)
11. **get_analysis_field() dispatch修復** (cache_key, target_date, if/elif全体)
12. **CI設定修正** (flake8 --extend-exclude に .venv追加)

**デプロイ**: v2.6.2（コミット `c56eb93`）→ Render本番に自動デプロイ済み  
**確認**: `curl https://rishiri-kelp-forecast-system.onrender.com/health?v=262` → `{"version":"2.6.2"}` ✅  
**/quick-review**: CRITICAL=0件 → **Go ✅**

**残り課題（v2.7.0バックログ）**:
- LINE `/api/line/status` 認証追加
- flask-limiter → Redis移行
- CORSステージングURL追加（必要になった時点で）
- `_FIELD_CACHE_TTL` → Redis移行

**次回やること**: 5/31リリースに向けて残MAJOR対応 or 漁師さんへの共有準備

---

### 2026-05-25（AI社員チーム整備）
**実施内容**: Coworkでリリース前チェック体制を一式構築  
**作成したもの**:
- `ai_review_agents/` 配下に専門AI社員14名分のMDファイル
  - タブ系5名（地図・エマグラム・島内分布・長期予報・ダッシュボード）
  - 機能系5名（通知・LINEテキスト・チャットボット・アルゴリズム・データ同期）
  - インフラ系3名（APIバックエンド・PWA・性能セキュリティ）
  - 統括1名（リリース判定・Claude Codeプロンプト生成）
- `AGENT_orchestrator.md`（Claude Code専用・grep駆動型）
- `.claude/commands/full-review.md`（`/full-review` スラッシュコマンド）
- `.claude/commands/quick-review.md`（`/quick-review` スラッシュコマンド）
- `AGENT_gmail_router.md`（GitHub通知→担当社員振り分け）
- Gmail毎朝9時自動チェックのスケジュールタスク（Cowork）
- `AI_MEMORY.md`（本ファイル）
- `RELEASE_GUIDE_FOR_FISHERMEN.md`（漁師さん向け試供品案内）
- `CLAUDE.md` 冒頭にAI_MEMORY.md参照を追記

**主な発見**: コードレビューは未実施。設計・ドキュメント整備のみ。  
**決定事項**:
- スキルMD・チケットMDは今週不要（GitHub Issuesで代替）
- Gmailルーターは Claude Code では動かない（Cowork専用）
- `/full-review` は Claude Code で、Gmailチェックは Cowork で行う役割分担を確立

**次回やること**: Claude Codeで `/full-review` を実行してCRITICAL問題を洗い出す  

---

## 📝 追記ルール

AI社員がこのファイルを更新するときは：
1. 「現在の既知問題」テーブルに問題を追加する（解決したら「解決済み」に移動）
2. 「レビュー実施履歴」に今日の結果を記録する
3. 「セッションログ」に作業メモを追記する（古いものは残す）
4. 「確定した設計判断」は追加できるが、削除・変更は人間だけが行う

