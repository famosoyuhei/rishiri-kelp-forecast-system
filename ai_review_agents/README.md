# AI社員チーム — 利尻島昆布干場予報システム 最終チェックガイド

## 概要

このフォルダには、リリース前最終チェック用のAI社員18名が格納されています。  
各ファイルをClaudeとの会話に貼り付けて（またはCLAUDE.mdとして配置して）、  
担当領域の精査を依頼してください。

---

## AI社員一覧

### タブ・画面系（5名）

| ファイル | 担当 | 主な確認対象 |
|---------|------|------------|
| `AGENT_map_tab.md` | 🗺️ 地図タブ担当 | 334地点マーカー・フィルタ・干場カード |
| `AGENT_emagram_tab.md` | 📈 エマグラムタブ担当 | 気温線・露点線・高層データ表示 |
| `AGENT_field_analysis_tab.md` | 🌐 島内分布タブ担当 | Leaflet移行・score/wind/solar図 |
| `AGENT_seasonal_tab.md` | 📅 長期予報タブ担当 | 月別見通し・ENSO情報 |
| `AGENT_dashboard_mobile.md` | 📊 ダッシュボード・モバイル担当 | dashboard.html・モバイル画面 |

### 機能系（5名）

| ファイル | 担当 | 主な確認対象 |
|---------|------|------------|
| `AGENT_notification.md` | 🔔 通知システム担当 | 16:00/01:30アラート・干場別設定 |
| `AGENT_line_text.md` | 💬 LINEテキスト担当 | 通知文言・チャット文章品質 |
| `AGENT_chatbot.md` | 🤖 チャットボット担当 | 干場アシスタント・パターン網羅性 |
| `AGENT_forecast_algorithm.md` | ⚗️ 予報アルゴリズム担当 | 閾値・地形補正・スコア計算 |
| `AGENT_data_sync.md` | 📂 データ同期担当 | 4ファイル同期・5条件削除制限 |

### インフラ系（3名）

| ファイル | 担当 | 主な確認対象 |
|---------|------|------------|
| `AGENT_api_backend.md` | 🔌 APIバックエンド担当 | 13エンドポイント・エラー処理 |
| `AGENT_pwa_offline.md` | 📱 モバイル/PWA担当 | Service Worker・オフライン同期 |
| `AGENT_security_perf.md` | 🔒 性能・セキュリティ担当 | 速度・認証・CORS・バリデーション |

### 外部連携・分析系（5名）

| ファイル | 担当 | 主な確認対象 |
|---------|------|------------|
| `AGENT_line_operation.md` | 📲 LINE通知配信・コマンド担当 | Webhook・登録/解除・沖止め |
| `AGENT_line_ux_flow.md` | 🌊 LINE登録UXフロー担当 | 登録導線・ニックネーム・QRヘルプ |
| `AGENT_upstash_persistence.md` | 💾 Upstash Redis永続化担当 | 通知データ永続化・診断 |
| `AGENT_amedas_accuracy.md` | 📡 実測データ収集・予報精度管理担当 | JMA実測・forecast_history・精度API |
| `AGENT_accuracy_spreadsheet_auditor.md` | 🧮 精度分析スプレッドシート監査担当 | Google Sheets・n8n・精度Dashboard |

### 統括（1名）

| ファイル | 担当 | 主な確認対象 |
|---------|------|------------|
| `AGENT_release_coordinator.md` | 🎯 リリース統括担当 | 全員の報告を集約→Claude Code修正プロンプト生成 |

---

## 使い方

### ステップ1：各AI社員に精査を依頼する

Claudeとの会話で、各MDファイルの内容を冒頭に貼り付けてから  
「このAI社員として、以下のファイルを確認してください」と依頼します。

例：
```
[AGENT_map_tab.mdの内容を貼り付け]

kelp_drying_map.htmlの地図タブ部分（L1〜L500付近）を確認してください。
```

または、`ai_review_agents/` フォルダを `CLAUDE.md` に追記して  
Claude Codeが自動で読み込むよう設定することもできます。

### ステップ2：報告書を集める

各AI社員は以下の形式で問題を報告します：

```
【重大度】🔴高 / 🟡中 / 🟢低
【該当箇所】ファイル名:行番号
【問題内容】〜〜
【修正提案】〜〜
```

### ステップ3：統括AI社員に集約を依頼する

`AGENT_release_coordinator.md` を使って、全員の報告を貼り付けると  
優先度順に整理されたClaude Code向け修正依頼プロンプトが生成されます。

---

## 推奨作業順序

```
1日目：① 地図タブ ② エマグラムタブ ③ 島内分布タブ
2日目：④ 長期予報タブ ⑤ ダッシュボード/モバイル ⑥ 通知システム
3日目：⑦ LINEテキスト ⑧ チャットボット ⑨ 予報アルゴリズム
4日目：⑩ データ同期 ⑪ APIバックエンド ⑫ PWA/オフライン
5日目：⑬ 性能・セキュリティ → ⑭ 統括：全報告集約 → Claude Code修正依頼
6〜7日目：修正実装 → 再チェック
```

---

**作成日**: 2026年5月24日  
**対象バージョン**: v2.6.0
