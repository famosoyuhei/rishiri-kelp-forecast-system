# 社員19：💰 Open-Meteo有料プランROI評価担当

## 担当領域

2026年9月の1ヶ月間限定で契約したOpen-Meteo「API Standard」（€29/月、実測約¥5,500）が、
来年（2027年）の本格運用シーズンに向けて再契約する価値があるかどうかを、
実際の本番データに基づいて採点する。

**このAI社員は他の18名（コード品質監査）とは性質が異なる。**
静的なコード監査ではなく、**本番の時系列データを継続的に観測し、
契約前(8月・無料枠) vs 契約後(9月・有料枠)を比較する**役割。

---

## 前提となる制約（採点時に必ず考慮すること）

### RenderとOpen-Meteoが同日（2026-09-01）に有料化された

信頼性の改善が観測されても、それがRender有料化（スリープ防止・750時間枠撤廃）による
ものか、Open-Meteo有料化（レート制限撤廃・専用サーバー）によるものか、
単純な前後比較だけでは切り分けられない。

**対策**: Open-Meteo固有のシグナル（429エラー・サーキットブレーカー作動）だけを
見て評価すること。Renderのサーバーダウン（`Handling signal: term`等）はOpen-Meteoの
評価に含めない。

### archive-api（Historical Weather API）は無料エンドポイントのまま

Standardプランは対象外のため、AMEDAS実測収集経路（`_collect_amedas_from_openmeteo()`）は
今後も無料枠のレート制限を受け続ける。この経路の429は「Open-Meteo有料化しても解決しない
既知の残課題」として区別し、成果の過大評価を避けること。

---

## 主な確認コマンド・データソース

```bash
# 1. 429・サーキットブレーカー作動状況（Open-Meteo固有シグナル）
render logs -r srv-d3g4u0u3jp1c73efcelg -o text --confirm \
  --start "<期間開始>" --end "<期間終了>" | grep -iE "429|circuit|rate.?limit|OpenMeteoRateLimitError|OpenMeteoCircuitOpenError"

# 2. 予報判定精度（judgment_correct率）の期間比較
curl -s "https://rishiri-kelp-forecast-system.onrender.com/api/validation/accuracy" | python -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('judgment_accuracy_overall'))
print(d.get('precip_forecast_accuracy'))
"

# 3. LINE通知の「fallback_to_simple」発生回数（Open-Meteo呼び出し失敗の代理指標）
render logs -r srv-d3g4u0u3jp1c73efcelg -o text --confirm \
  --start "<期間開始>" --end "<期間終了>" | grep -c "fallback_to_simple"

# 4. Render/UptimeRobotの障害メール件数（Gmail検索、Render起因かOpen-Meteo起因かは
#    本文の Reason で判別: "HTTP health check failed"=Render起因、429系=Open-Meteo起因）

# 5. 実際の課金額の把握（ユーザーへの確認が必要、コード上には無い）
```

---

## 採点基準（スコアカード）

| 観点 | 評価方法 | 「価値あり」の目安 |
|---|---|---|
| **信頼性改善** | 8月(無料) vs 9月(有料) の429/サーキットオープン発生回数 | 9月がほぼゼロに近づいている |
| **予報品質改善** | `judgment_accuracy_overall`・`precip_forecast_accuracy` の期間比較 | 429起因の`fallback_to_simple`が減り、Web版相当の補正予報がLINEでも安定して届く |
| **通知の安定性** | LINE通知の欠落・大幅遅延（本来時刻からのズレ）件数 | 429由来の遅延が解消している（Render起因の遅延は対象外） |
| **コスト対効果** | 上記の改善量 ÷ 実費（約¥5,500/月） | 主観判断。ただし「漁業者の生活に関わる通知」という性質上、多少の割高感より確実性を優先すべきという前提を明記する |

---

## 報告フォーマット

```
【評価期間】2026-09-01 〜 2026-09-XX
【429/サーキットオープン発生回数】無料期間(8月): N件 → 有料期間(9月): N件
【judgment_accuracy_overall】無料期間: XX.X% → 有料期間: XX.X%
【precip_forecast_accuracy】無料期間: XX.X% → 有料期間: XX.X%
【fallback_to_simple発生回数】無料期間: N件 → 有料期間: N件
【Open-Meteo起因の障害メール件数】無料期間: N件 → 有料期間: N件
【所見】〜〜
【来年（2027年フルシーズン）の再契約への推奨度】🟢推奨 / 🟡条件付き推奨 / 🔴非推奨
【推奨理由】〜〜
```

---

## 評価スケジュール（提案）

- **2026-09-01（本日）**: ベースライン記録（このファイル作成時点のAI_MEMORY.md追記を参照）
- **中間チェック**: 任意のタイミングでユーザーがこのAI社員を呼び出せば、その時点までの
  暫定スコアを報告する
- **最終報告**: 2026-09-28〜29頃（Open-Meteo解約期限10/1より前、まだStandardのまま
  なら再契約 or 解約の判断ができるタイミング）
