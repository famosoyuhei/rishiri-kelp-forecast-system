# AIマーケティング社員チーム — 売り出し設計ガイド

## 概要

このフォルダには、利尻島昆布干場予報システムと、全国一次産業向けの天候予測アプリ導入支援を広げるためのAI社員を格納しています。

レビュー担当の `ai_review_agents/` とは違い、こちらは **誰に、何を、どの言葉で、どの導線から届けるか** を設計する営業・広報・コピーライティング部隊です。

---

## 2つの売り出し方向

### 方向A：利尻島内の昆布関係者向け

目的は、アプリそのものを使ってもらうことです。

大切にする言葉:

- 利尻の昆布は、利尻の天気で予報する
- 経験と勘を否定せず、判断材料を増やす
- 今年の干し判断を、地域の記録で守る

対象:

- 昆布漁師
- 昆布干し担当の家族・雇用者
- 漁協・部会・地域の世話役
- 若手後継者
- 役場・地域振興担当

### 方向B：全国一次産業向け

目的は、利尻アプリをそのまま売ることではありません。

**天候で収支がブレる現場に、専用の予測・記録・通知アプリを導入する支援** として提案します。

全国向けは、業種・地域・作業判断が十人十色のため、相談とヒアリングを必須の入口にします。
島内向けの自由使用とは分けて扱ってください。

対象例:

- 農業法人
- 漁業法人
- JA部会・生産者組織
- 水産加工・養殖事業者
- 牧草・露地野菜・果樹・茶・乾燥作物などの生産者
- 農機具店・資材店・ドローン散布事業者
- 地方銀行・信用金庫の農業支援担当

---

## AI社員一覧

| ファイル | 担当 | 主な成果物 |
|---|---|---|
| `AGENT_rishiri_stakeholder_mapper.md` | 利尻島内ステークホルダー理解担当 | 島内ターゲット整理、初回接触順、紹介導線 |
| `AGENT_rishiri_kombu_copywriter.md` | 利尻昆布向けコピーライター | チラシ、LINE文、説明文、見出し |
| `AGENT_rishiri_demo_script_director.md` | 島内説明会・デモ台本担当 | 5分/15分/30分デモ台本、質疑応答 |
| `AGENT_primary_industry_needs_researcher.md` | 全国一次産業ニーズ調査担当 | 業種別ニーズ仮説、優先市場リスト |
| `AGENT_industry_usecase_designer.md` | 業種別ユースケース設計担当 | 業種別アプリ案、機能パッケージ |
| `AGENT_trust_channel_developer.md` | 信頼導線・紹介ルート開拓担当 | ランサーズ/ココナラ外の到達導線、提携候補 |
| `AGENT_sns_editor_in_chief.md` | SNS編集長 | 投稿カレンダー、投稿順、島内/全国の切り分け |
| `AGENT_rishiri_island_sns_operator.md` | 島内SNS投稿担当 | 島内向け広告文、LINE転送文、LP冒頭文 |
| `AGENT_sns_fact_checker.md` | SNS事実確認・誇大表現防止担当 | 実装根拠チェック、禁止表現チェック |
| `AGENT_microtargeting_planner.md` | 島内SNSターゲティング設計担当 | 地域・季節・言葉・画像・導線の絞り込み |
| `AGENT_sns_response_analyst.md` | SNS反応分析・改善担当 | 週次レポート、コメント分類、次週改善 |
| `AGENT_x_primary_industry_operator.md` | X全国一次産業発信担当 | X単発投稿、スレッド、固定投稿 |
| `AGENT_threads_field_storyteller.md` | Threads現場ストーリー担当 | やわらかい現場文脈投稿、連投、Instagram連携文 |
| `AGENT_note_case_study_writer.md` | note事例記事担当 | 事例記事、記事構成、SNS展開文 |
| `AGENT_sns_calendar_planner.md` | SNS投稿カレンダー設計担当 | 4週間投稿計画、承認キューCSV |
| `AGENT_sns_approval_publisher.md` | SNS承認・自動投稿オペレーション担当 | 承認ルール、投稿前チェック、投稿後ログ |

---

## 推奨作業順序

1. `AGENT_rishiri_stakeholder_mapper.md`
2. `AGENT_rishiri_kombu_copywriter.md`
3. `AGENT_rishiri_demo_script_director.md`
4. `AGENT_primary_industry_needs_researcher.md`
5. `AGENT_industry_usecase_designer.md`
6. `AGENT_trust_channel_developer.md`
7. `AGENT_sns_fact_checker.md`
8. `AGENT_sns_editor_in_chief.md`
9. `AGENT_microtargeting_planner.md`
10. `AGENT_rishiri_island_sns_operator.md`
11. `AGENT_sns_response_analyst.md`
12. `AGENT_x_primary_industry_operator.md`
13. `AGENT_threads_field_storyteller.md`
14. `AGENT_note_case_study_writer.md`
15. `AGENT_sns_calendar_planner.md`
16. `AGENT_sns_approval_publisher.md`

島内向けの言葉と全国向けの言葉は混ぜないでください。

島内向けは **信頼・共同性・現場感**。  
全国向けは **収支・作業判断・導入支援・再現性・相談必須**。

X、Threads、noteは全国向けを主用途にしてください。

- X: 一次産業・スマート農業/水産・支援者へ問題提起と導入支援を届ける
- Threads: 開発思想、現場への敬意、地域専用アプリの考え方をやわらかく伝える
- note: 利尻島の実例を長文ケーススタディ化し、X/Threadsから誘導する

---

## 共通の出力形式

各AI社員は最後に以下を出してください。

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[担当名] — 出力完了
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

今回作ったもの:
1. ...
2. ...
3. ...

次に必要な素材:
1. ...
2. ...

そのまま使える一文:
「...」
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
