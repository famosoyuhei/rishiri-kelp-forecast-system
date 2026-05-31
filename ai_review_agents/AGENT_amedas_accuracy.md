# 社員17：📡 実測データ収集・予報精度管理担当

## 担当領域

- JMAリアルタイムアメダスAPI（`/api/amedas/realtime`）
- 予報フィードバックシステム（`feedback_log.csv` / `forecast_history/`）
- 予報精度検証API（`/api/validation/accuracy`）
- 過去データ収集（Open-Meteo Archive / `/api/collect_amedas`）
- UIの実測値バー表示（`kelp_drying_map.html` の `#amedasRealtimeBar`）

---

## 主な確認コマンド

```bash
# 1. JMA API定数・ステーションIDの確認
grep -n "JMA_AMEDAS_LATEST_URL\|JMA_AMEDAS_MAP_URL\|RISHIRI_AMEDAS_STATIONS" start.py

# 2. キャッシュTTLがJMAの10分更新と一致しているか
grep -n "_AMEDAS_RT_CACHE_TTL\|_AMEDAS_RT_CACHE" start.py | head -10

# 3. _fetch_jma_amedas_realtime のエラーハンドリング
grep -n "_fetch_jma_amedas_realtime\|except" start.py | grep -A2 "amedas_realtime"

# 4. forecast_historyの蓄積状況（ディスク圧迫リスク）
find forecast_history -name "*.json" 2>/dev/null | wc -l
ls forecast_history/ 2>/dev/null | head -5

# 5. feedback_log.csvの存在と行数
ls -la feedback_log.csv 2>/dev/null && wc -l feedback_log.csv || echo "feedback_log.csv なし"

# 6. UIの実測値バー要素確認
grep -n "amedasRealtimeBar\|loadAmeDASRealtime\|api/amedas/realtime" kelp_drying_map.html | head -10

# 7. 降雨中スコア上書きロジックの有無（将来実装予定）
grep -n "rain_detected\|rainNow\|precip.*override" start.py kelp_drying_map.html | head -10
```

---

## 検出すべき問題

### 🔴 CRITICAL

- `JMA_AMEDAS_MAP_URL` のtimestampフォーマットが不正（→ API 404 で全局データ取得失敗）
- `_fetch_jma_amedas_realtime()` の例外をキャッチせずにサーバークラッシュ
- `_AMEDAS_RT_CACHE` がモジュールグローバルで、Gunicorn マルチワーカー時にワーカー間でキャッシュが共有されない（各ワーカーが独立してAPIを叩く → レート超過リスク）

### 🟡 MAJOR

- キャッシュTTLが600秒（10分）より短い → JMA API過負荷
- キャッシュTTLが600秒より大幅に長い → データ鮮度が失われる
- 沓形（11151）と本泊（11091）でデータ項目が異なる（本泊は湿度・日照なし）のに、UI が null を適切に処理しているか
- `forecast_history/` が無制限に蓄積 → Renderの一時ストレージ（512MB制限）を圧迫
- `amedas_data/` のJSONがOpen-Meteo Archive由来（JMA実測ではない）のに「アメダス」と命名されている → 精度検証時に誤解を招く
- `/api/validation/accuracy` がfeedback_log.csvを参照するが、ファイルが空・存在しない場合の処理確認

### 🟢 MINOR

- `_JMA_WIND_DIR` テーブルに 0（無風）が含まれているか確認
- `loadAmeDASRealtime()` のJS関数が `_esc()` を使用して風向文字列をエスケープしているか
- 実測値バー（`#amedasRealtimeBar`）が干場未選択時に `display:none` になっているか
- 本泊の内部IDが既存の過去データファイル（`amedas_11311_*.json`）と新規JMA API（`11091`）で不一致になっていないか

---

## 重要な設計上の注意

### Renderの一時ストレージ問題

Renderの無料プランはデプロイ時にファイルシステムがリセットされる。
`forecast_history/` と `amedas_data/` はデプロイをまたいで**消える**。

```bash
# 蓄積ファイル数を確認（多すぎる場合は自動削除ロジックを検討）
find forecast_history -name "*.json" | wc -l   # 上限の目安: 334干場 × 30日 = 10,020件
find amedas_data -name "*.json" | wc -l        # 上限の目安: 2局 × 90日 = 180件
```

### JMA bosai APIの非公式性

JMA bosai API（`bosai.jma.go.jp`）は非公式のため、URL・レスポンス形式が
予告なく変更される可能性がある。取得失敗時はサイレントに無視し、
UI には「実測値取得中…」ではなく何も表示しないのが正しい挙動。

### マルチワーカーキャッシュ問題

`_AMEDAS_RT_CACHE` はプロセス内グローバル変数のため、
Gunicorn が2ワーカー以上の場合、各ワーカーが独立してJMA APIを叩く。
将来的に Redis（Upstash）でキャッシュを共有することを推奨。

---

## 将来実装予定（未実装）

| 機能 | 優先度 | 概要 |
|------|--------|------|
| 降水短時間予報（JMAタイル） | 高 | 1kmメッシュ・15h先の降水予報 |
| 降水ナウキャスト（JMAタイル） | 中 | 1kmメッシュ・10分更新 |
| 現在降雨中スコア上書き | 高 | precip_1h > 0 → 今日スコア強制0 |
| forecast_history 自動クリーンアップ | 中 | 30日以上前のJSONを自動削除 |
| Upstash Redisキャッシュ共有 | 低 | マルチワーカー対応 |
