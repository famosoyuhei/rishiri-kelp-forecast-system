# 🚦 AI社員：レビュー自動実行オーケストレーター（Claude Code専用版）

## このファイルの使い方

プロジェクトルートで `claude` を起動し、以下のように依頼してください：

```bash
cd /path/to/rishiri_konbu_weather_tool
claude
```

```
AGENT_orchestrator.mdを読んで、フルレビューを実行してください。
```

---

## あなたの役割

あなたは **Claude Code** として動作する自律レビューエージェントです。  
`grep`・`Read`（部分読み）・`Bash` を組み合わせて大きなファイルを効率よく調べ、  
13名分のチェックリストを順番にこなし、最後に統括プロンプトを生成してください。

**絶対に守ること：**
- `kelp_drying_map.html`（6,235行）と `start.py`（4,363行）を**丸ごと読まない**
- 常に `grep -n` でキーワードを探してから、その前後50〜100行だけを `Read` する
- 1社員ごとに報告書を出力してから次の社員に進む（コンテキストを圧迫しない）

---

## PHASE 0：準備確認（必ず最初に実行）

```bash
# ファイル存在確認
ls ai_review_agents/AGENT_*.md | wc -l          # 16以上あればOK
wc -l start.py kelp_drying_map.html              # 行数確認
ls hoshiba_spots.csv hoshiba_records.csv all_spots_array.js
ls service-worker.js manifest.json Procfile 2>/dev/null || echo "PWA関連ファイルなし"

# 4ファイル地点数の整合性チェック
grep -c "^H_\|^A_\|^R_" hoshiba_spots.csv
grep -c "H_\|A_\|R_" all_spots_array.js
```

確認後、「準備完了。15名のレビューを開始します。」と宣言してください。

---

## PHASE 1：15名のレビュー実行

各社員のレビューは **grep → 部分Read → 判定** の流れで実行します。  
レビュー完了後は以下のセパレーターを出力してから次へ進んでください：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 [番号]. [社員名] 報告書 — 完了 （🔴X件 🟡X件 🟢X件）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 社員1：🗺️ 地図タブ担当

```bash
# 334地点の存在確認
grep -c "H_\|A_\|R_" all_spots_array.js

# 特別地点3箇所の座標確認
grep -n "A_1783_1383\|A_2417_1867\|R_1800_2392" hoshiba_spots.csv all_spots_array.js

# ニックネーム機能のlocalStorage実装確認
grep -n "nickname\|ニックネーム\|localStorage" kelp_drying_map.html | head -20

# 削除ボタンの特別地点保護確認
grep -n "delete\|削除" kelp_drying_map.html | grep -i "A_\|R_\|special\|protect" | head -10

# フィルタ（町→地区→部落）の実装確認
grep -n "町\|地区\|部落\|filter\|Filter" kelp_drying_map.html | head -20

# 風名ファイルの16方位確認
grep -c "風" rishiri_wind_names.js
```

**報告形式（各チェック項目ごとに）：**
```
✅ [項目名] 異常なし  または
【重大度】🔴/🟡/🟢
【該当箇所】ファイル名:行番号
【問題内容】〜
【修正提案】〜
```

---

### 社員2：📈 エマグラム担当

```bash
# エマグラム描画ロジックの存在確認
grep -n "emagram\|エマグラム\|850hPa\|700hPa\|500hPa" kelp_drying_map.html | head -20

# エマグラム関連の行番号を取得してから周辺を部分Read
grep -n "drawEmagram\|renderEmagram\|emagramCanvas" kelp_drying_map.html | head -5

# 露点線の描画確認
grep -n "dewpoint\|露点\|dew_point" kelp_drying_map.html | head -10

# エラー時フォールバックの確認
grep -n "emagram" kelp_drying_map.html | grep -i "error\|fail\|catch\|fallback" | head -10

# Open-Meteo 高層データ取得確認
grep -n "pressure_level\|geopotential_height\|temperature_850\|windspeed_850" start.py | head -10
```

---

### 社員3：🌐 島内分布タブ担当

```bash
# タブ名の確認（「等値線解析」→「島内分布」への変更）
grep -n "等値線解析\|島内分布\|contour\|field" kelp_drying_map.html | head -10

# 新APIエンドポイントの確認
grep -n "api/analysis/field\|api/analysis/contours" start.py kelp_drying_map.html | head -20

# matplotlibの残存確認（廃止されているはず）
grep -n "matplotlib\|pyplot\|plt\." start.py | head -10

# Leaflet CircleMarkerの実装確認
grep -n "CircleMarker\|L\.circle\|leaflet" kelp_drying_map.html | head -10

# typeパラメータの実装確認（score/wind/humidity/temperature/solar）
grep -n "type.*score\|type.*wind\|type.*solar" start.py | head -10
```

---

### 社員4：📅 長期予報タブ担当

```bash
# seasonal_outlookエンドポイントの確認
grep -n "seasonal_outlook\|シーズン\|長期予報" start.py | head -10

# 表示月の自動算出ロジック確認
grep -n "month\|月" kelp_drying_map.html | grep -i "season\|シーズン\|forecast" | head -10

# JSTでの月判定確認
grep -n "JST\|UTC\+9\|timezone\|pytz\|ZoneInfo" start.py | head -10

# ENSO情報の表示確認
grep -n "ENSO\|エルニーニョ\|ラニーニャ\|高気圧" kelp_drying_map.html | head -10

# 免責文の確認
grep -n "参考\|免責\|JMA\|気象庁" kelp_drying_map.html | head -10
```

---

### 社員5：📊 ダッシュボード・モバイル担当

```bash
# app_icon.pngの3ファイル統一確認
grep -n "app_icon" kelp_drying_map.html dashboard.html mobile_forecast_interface.html 2>/dev/null

# モバイルのviewport設定確認
grep -n "viewport\|meta name" mobile_forecast_interface.html 2>/dev/null | head -5

# ダッシュボードのAPIエンドポイント参照確認
grep -n "api/forecast\|api/spots" dashboard.html 2>/dev/null | head -10

# モバイルのタッチターゲットサイズ確認（44px以上）
grep -n "height.*px\|min-height" mobile_forecast_interface.html 2>/dev/null | head -10
```

---

### 社員6：🔔 通知システム担当

```bash
# shouldSendNotification関数の存在確認
grep -n "shouldSendNotification" kelp_drying_map.html | head -10

# 16:00 JST通知のスケジューリング確認
grep -n "16:00\|16,0\|scheduleEvening\|夕方通知" kelp_drying_map.html | head -10

# 01:30 JST通知の確認
grep -n "01:30\|1,30\|scheduleEarlyMorning\|早朝" kelp_drying_map.html | head -10

# 緊急アラートの閾値（30点）確認
grep -n "30\|urgent\|emergency\|緊急\|急変" kelp_drying_map.html | grep -i "score\|スコア\|alert" | head -10

# localStorage保存キー名確認（hoshibaNotificationData）
grep -n "hoshibaNotificationData\|notificationData" kelp_drying_map.html | head -10

# 沖止め日スキップの確認
grep -n "沖止め\|okidome\|skipDate\|skip" kelp_drying_map.html | head -10
```

---

### 社員7：💬 LINEテキスト担当

```bash
# 通知文言の取得（通知メッセージ生成部分）
grep -n "notification.*body\|message.*body\|通知.*文\|干せます\|干せません" kelp_drying_map.html | head -20

# 文字数の長い通知文を検出（120文字超の可能性）
grep -n "title:\|body:" kelp_drying_map.html | head -20

# 絵文字の使用確認（文字化けリスクのある絵文字を検出）
grep -n "emoji\|☀️\|🌧️\|⚠️\|🌊" kelp_drying_map.html | head -10

# 部落名の表記確認
grep -n "鴛泊\|沓形\|仙法志\|鬼脇" kelp_drying_map.html | head -10

# テキストコピー機能の確認
grep -n "copy\|clipboard\|クリップボード\|コピー" kelp_drying_map.html | head -10
```

---

### 社員8：🤖 チャットボット担当

```bash
# CHAT_PATTERNSの行数・パターン数確認
grep -n "CHAT_PATTERNS\|processMessage" kelp_drying_map.html | head -5

# CHAT_PATTERNSが始まる行番号を取得
START=$(grep -n "CHAT_PATTERNS" kelp_drying_map.html | head -1 | cut -d: -f1)
echo "CHAT_PATTERNS開始行: $START"

# 部落名カバレッジ確認（主要部落が含まれているか）
grep -n "沓形\|鴛泊\|仙法志\|鬼脇\|野塚\|本泊" kelp_drying_map.html | grep -i "pattern\|keyword\|match" | head -20

# 方位比較の動的計算確認（山頂座標使用）
grep -n "R_1800_2392\|45\.1800\|141\.2392\|方位\|bearing\|azimuth" kelp_drying_map.html | head -10

# エラーハンドリング（空入力・長文）
grep -n "trim\|length\|maxLength\|空\|empty" kelp_drying_map.html | grep -i "chat\|message\|input" | head -10

# 詳細モードのキーワード確認
grep -n "詳しく\|初心者\|わかりやすく\|detailMode\|detail_mode" kelp_drying_map.html | head -10
```

---

### 社員9：⚗️ 予報アルゴリズム担当

```bash
# 降水量の絶対条件確認（== 0 か < 1 か）
grep -n "precipitation" start.py | grep -v "#" | head -20

# 風速・湿度閾値の確認
grep -n "2\.0\|wind_speed.*2\|humidity.*94\|94.*humidity" start.py | head -10

# 地形補正の実装確認（L847-L863付近）
grep -n "is_forest\|is_coastal\|wind_speed -=\|wind_speed +=\|humidity +=" start.py | head -20

# 気温補正が削除されているか確認（あったらバグ）
grep -n "temperature.*correction\|temp.*補正\|elevation.*temp\|temp.*elevation" start.py | grep -v "#" | head -10

# calculate_enhanced_drying_score関数の確認
grep -n "calculate_enhanced_drying_score\|drying_score" start.py | head -10

# 日射量パラメータの確認
grep -n "solar_radiation\|shortwave_radiation\|direct_radiation" start.py | head -10

# 負の風速値のガード確認
grep -n "max(0\|max(wind\|wind.*max" start.py | head -10
```

---

### 社員10：📂 データ同期担当

```bash
# 4ファイルの地点数整合性チェック
echo "=== CSV地点数 ===" && grep -c "." hoshiba_spots.csv
echo "=== JS地点数 ===" && grep -c "H_\|A_\|R_" all_spots_array.js
echo "=== KML地点数 ===" && grep -c "<Placemark" hoshiba_spots_named.kml 2>/dev/null || echo "KMLなし"
echo "=== Records（特別地点なし確認）===" && grep -c "A_\|R_" hoshiba_records.csv 2>/dev/null || echo "Records正常（特別地点なし）"

# /add エンドポイントの同期処理確認
grep -n "def add\|@app.route.*add\|hoshiba_spots.csv\|all_spots_array.js\|hoshiba_spots_named.kml" start.py | head -20

# /delete の5条件制限確認（L985-L996付近）
grep -n "def delete\|L985\|L986\|L987\|L988\|L989\|L990\|L991\|L992\|L993\|L994\|L995\|L996" start.py | head -5
# 実際の行を読む
grep -n "記録.*exist\|favorite\|お気に入り\|notification.*used\|lock\|機械学習" start.py | head -20

# 特別地点の削除保護確認
grep -n "A_\|R_\|special\|protect\|cannot.*delete\|削除.*不可" start.py | grep -i "delete\|remove" | head -10
```

---

### 社員11：🔌 APIバックエンド担当

```bash
# 全13エンドポイントの存在確認
grep -n "@app.route" start.py | head -20

# JSTタイムゾーン統一の確認
grep -n "datetime.now()\|datetime\.utcnow()\|timezone\|JST\|pytz\|ZoneInfo" start.py | head -20

# Open-Meteo タイムアウト設定確認
grep -n "timeout\|requests.get\|requests.post" start.py | head -10

# elevation パラメータの全呼び出し追加確認
grep -n "open-meteo\|api.open-meteo\|elevation" start.py | head -10

# shortwave_radiation・dewpoint_2mの取得確認
grep -n "shortwave_radiation\|dewpoint_2m\|precipitation_probability" start.py | head -10

# エラーハンドリングの確認（try/except）
grep -n "except\|try:" start.py | wc -l
grep -n "return.*503\|return.*400\|return.*404" start.py | head -10

# Procfileの確認
cat Procfile
```

---

### 社員12：📱 PWA担当

```bash
# manifest.jsonの確認
cat manifest.json 2>/dev/null || echo "manifest.json なし（🔴CRITICAL）"

# Service Workerの確認
ls service-worker.js sw.js 2>/dev/null || echo "SW ファイルなし（🔴CRITICAL）"

# SWの登録コード確認
grep -n "serviceWorker.register\|navigator.serviceWorker" kelp_drying_map.html | head -5

# キャッシュ対象ファイルの確認
cat service-worker.js 2>/dev/null | grep -n "cache\|CACHE" | head -20

# オフライン仮保存の実装確認
grep -n "offline\|オフライン\|仮保存\|pendingSave\|localStorage" kelp_drying_map.html | head -20

# iOS対応メタタグ確認
grep -n "apple-mobile-web-app\|apple-touch-icon" kelp_drying_map.html | head -5

# HTTPS確認（Renderはデフォルトでhttps）
grep -n "https://rishiri-kelp-forecast" start.py Procfile 2>/dev/null | head -5
```

---

### 社員13：🔒 性能・セキュリティ担当

```bash
# ハードコードされたAPIキー・シークレットの検出
grep -n "api_key\|secret\|password\|token" start.py | grep -v "#" | grep -v "os.environ\|os.getenv\|config\." | head -10

# .gitignoreの確認
cat .gitignore 2>/dev/null | head -20

# innerHTML の直接使用（XSSリスク）
grep -n "innerHTML" kelp_drying_map.html | grep -v "textContent\|innerText" | head -10

# eval()の使用確認
grep -n "eval(" kelp_drying_map.html start.py | head -5

# CORS設定の確認
grep -n "CORS\|cors\|Access-Control\|flask_cors" start.py | head -10

# 入力バリデーション（緯度経度の範囲チェック）
grep -n "45\.\|141\.\|lat.*valid\|lon.*valid\|validate" start.py | grep -i "add\|spot\|coordinate" | head -10

# 並列リクエスト or キャッシュの確認（速度対策）
grep -n "ThreadPoolExecutor\|asyncio\|concurrent\|cache\|functools.lru_cache" start.py | head -10

# Renderのメモリ対策（matplotlibの削除確認）
grep -n "import matplotlib\|from matplotlib\|import pyplot" start.py | head -5
```

---

### 社員14：📲 LINE通知配信・コマンド担当

```bash
# Webhook署名検証の確認
grep -n "X-Line-Signature\|hmac\|sha256\|verify" line_integration.py | head -10

# parse_commandの優先順位確認（干場登録がstartswith前にあるか）
grep -n "干場登録\|register_guidance\|startswith" line_integration.py | head -15

# ペンディングアクション型のルーティング確認
grep -n "pa.get.*type\|nogo_date\|select_spot" line_integration.py | head -10

# notify_allのtarget_date計算確認（evening=翌日, morning=当日）
grep -n "day_number\|target_date\|timedelta" line_integration.py | head -10

# 漁期バリデーション（6〜9月、過去日付拒否）の確認
grep -n "_validate_season_date\|month < 6\|month > 9\|dt.date.*<.*today" line_integration.py | head -10

# テスト全件通過確認
python -m pytest tests/test_line_integration.py -q --tb=no 2>&1 | tail -3
```

AGENT_line_operation.md の全チェックリストに従って精査してください。

---

### 社員15：🌊 LINE登録UXフロー担当

```bash
# 呼び名必須ボタン制御の確認（pointer-events:none）
grep -n "pointer-events.*none\|lineRegisterNickHint\|lineNicknameHint" kelp_drying_map.html | head -10

# ★モーダルのspotId生表示が消えているか確認
grep -n "\${spotId}" kelp_drying_map.html | grep -i "modal\|div.*style" | head -5

# LINE URLスキームのアカウントID整合性
grep -n "@766cfpki" kelp_drying_map.html line_integration.py | head -10

# リッチメニューに沖止めボタンがないことを確認
grep -n "沖止め" line_integration.py | grep -i "btn\|rich\|menu\|BTNS" | head -5

# _HELP_QRに沖止めがないことを確認
grep -n "_HELP_QR\s*=" line_integration.py

# 設定確認がニックネーム表示か確認
grep -n "spot_nicknames\|nicknames\.get" line_integration.py | head -5

# フォロー時のQR付きヘルプ確認
grep -n "event_type.*follow" line_integration.py | head -5
```

AGENT_line_ux_flow.md の全チェックリストに従って精査してください。

---

## PHASE 2：進捗サマリーの表示

15名全員完了後、以下を出力してください：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ PHASE 1 完了 — 13名のレビュー結果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 CRITICAL（リリースブロッカー）: X件
🟡 MAJOR（推奨修正）           : X件
🟢 MINOR（改善提案）           : X件
合計                           : X件

問題が多かった領域 TOP3（15名中）:
1位: [社員名] — X件
2位: [社員名] — X件
3位: [社員名] — X件
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## PHASE 3：統括集約（AGENT_release_coordinator.mdに従って実行）

以下のすべてを生成してください：

**セクション1**: エグゼクティブサマリー＋Go/No-Go判定

**セクション2**: 優先度スコア順の修正リスト
（スコア = 致命度点数 × 影響人数 × 修正コスト逆数）

**セクション3**: Claude Codeへの修正依頼プロンプト — CRITICAL分  
冒頭に必ず以下のシステム情報を含めること：
```
# システム情報（修正時の制約）
- start.py: 4,363行 / kelp_drying_map.html: 6,235行
- 本番: https://rishiri-kelp-forecast-system.onrender.com
- 時刻: すべてJST（UTC+9）で統一
- 特別地点（A_/R_）: 削除禁止・記録禁止
- 4ファイル同期: CSV/KML/JS/Records は常に同時更新
- 閾値根拠: THRESHOLD_UPDATE_SUMMARY.md（実測21件）
```

**セクション4**: Claude Codeへの修正依頼プロンプト — MAJOR分

**セクション5**: v2.7.0バックログ

---

## PHASE 4：完了宣言

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 レビュー完了
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

次のアクション:
1. セクション3をこのセッションに貼り付けて「修正してください」と依頼
2. 修正後に「クイックモードで再チェック」を実行
3. CRITICAL 0件 → リリースGO ✅

推定残り作業時間: 約X時間（CRITICAL X件 + MAJOR Y件）
リリース目標（2026-05-31）まで: あとX日
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 実行モード

### フルモード（デフォルト）
全13名・全チェック項目を実行します。目安: 20〜40分

### クイックモード
🔴CRITICALに関わるgrepコマンドのみ実行します。目安: 5〜10分  
修正後の再確認に使用してください。

```bash
# クイックモード時に実行するコマンド群
grep -n "precipitation" start.py | grep "== 0\|< 1"          # 降水量閾値
grep -rn "innerHTML" kelp_drying_map.html | grep -v "Text"    # XSSリスク
grep -n "import matplotlib" start.py                           # メモリリスク
cat manifest.json 2>/dev/null || echo "PWAマニフェスト欠損"   # PWA
grep -c "^H_\|^A_\|^R_" hoshiba_spots.csv                    # 地点数整合性
```

### 単独社員モード
「社員9（予報アルゴリズム）だけ実行してください」のように指定できます。

---

## 中断・再開

「社員5まで完了しています。社員6から再開してください。」  
のように伝えれば、途中から再開できます。
