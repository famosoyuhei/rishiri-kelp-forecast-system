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
| 2 | 🟡 MAJOR | 社員9 | LINE `/api/line/status` エンドポイントに認証なし（誰でもLINE接続状況を確認可能） | 2026-05-25 | 未修正 |
| 3 | 🟡 MAJOR | 社員13 | `flask-limiter` のインメモリストレージ（Render再起動でリセット）。本番はRedis推奨 | 2026-05-25 | UserWarning出力中。機能は動作する |
| 4 | 🟡 MINOR | 社員12 | `_FIELD_CACHE_TTL` がインメモリ（Workerプロセス間でキャッシュ共有不可） | 2026-05-25 | Redis移行推奨。現状は動作する |

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

---

## 🗓️ 今週のスプリント状況

**リリース目標日**: 2026年5月31日（あと6日）

### 今日やること（2026-05-26）
- [x] ~~Claude Codeで `/full-review` を初回実行 → 問題リストを確定~~（5/25に完了）
- [x] ~~CRITICAL問題の修正に着手~~（5/25に全修正完了、v2.6.2デプロイ済み）
- [ ] GitHub Actions CIの最終パス確認（`c5c10a3` のRun Succeeded通知を待つ）

### 今週やること
- [x] ~~/full-review で問題リストを確定（5/26）~~（5/25に前倒し完了）
- [x] ~~CRITICAL問題をすべて修正（5/27〜28）~~（5/25に完了 CRITICAL 3→0）
- [x] ~~/quick-review で再チェック → CRITICAL 0件を確認（5/29）~~（5/25に完了）
- [ ] 残MAJOR 4件のうち優先度高いものを着手（LINE認証追加など）
- [ ] 漁師さんにURL＋RELEASE_GUIDE_FOR_FISHERMEN.mdを共有（5/31）

---

## 💬 セッションログ（新しい順）

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

