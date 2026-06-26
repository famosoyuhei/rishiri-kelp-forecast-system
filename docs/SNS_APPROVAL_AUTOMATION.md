# SNS投稿承認・自動投稿フロー設計

## 目的

投稿内容やペースをAI社員が計画し、ユーザーがGoogle Sheets上で内容確認してOKした投稿だけを自動投稿する。

この仕組みは、SNS運用を効率化しつつ、未確認投稿・誇大表現・実装と違う宣伝文の投稿を防ぐためのものです。

---

## 全体像

```text
AIマーケティング社員
  -> 投稿案を作成
  -> SNS事実確認AI社員が校閲
  -> Google Sheets 投稿キューへ登録
  -> ユーザーが status を approved に変更
  -> n8n が15分ごとに承認済み投稿を確認
  -> 媒体ごとに投稿
  -> 投稿結果を Google Sheets に書き戻す
```

---

## 必要ファイル

| ファイル | 役割 |
|---|---|
| `docs/google_sheets_sns_approval_calendar_apps_script.gs` | 投稿キュー用Google Sheetsを作成 |
| `docs/n8n_sns_approval_publishing_blueprint.json` | n8n自動投稿ワークフローの設計図 |
| `docs/SNS_CONTENT_CALENDAR_4WEEK.md` | 初回4週間の投稿計画 |
| `ai_marketing_agents/AGENT_sns_calendar_planner.md` | 投稿計画AI社員 |
| `ai_marketing_agents/AGENT_sns_approval_publisher.md` | 承認・投稿運用AI社員 |
| `ai_marketing_agents/AGENT_sns_fact_checker.md` | 事実確認AI社員 |

---

## Google Sheets タブ

### `post_queue`

投稿キュー本体です。

| 列 | 内容 |
|---|---|
| `post_id` | 投稿ID。一意 |
| `campaign` | `rishiri_island` / `national_primary_industry` |
| `audience` | `island` / `national` |
| `platform` | `facebook` / `instagram` / `x` / `threads` / `note` / `line_share` |
| `post_type` | `text` / `image` / `thread` / `article` / `line_text` |
| `status` | `draft` / `needs_review` / `approved` / `scheduled` / `published` / `error` / `hold` |
| `fact_check_status` | `unchecked` / `ok` / `needs_fix` / `blocked` |
| `scheduled_at_jst` | 投稿予定時刻 |
| `title` | 見出し |
| `body` | 投稿本文 |
| `cta` | 行動導線 |
| `url` | 投稿に添えるURL |
| `asset_url` | 画像/動画URL |
| `asset_notes` | 画像指示 |
| `approval_notes` | ユーザー確認メモ |
| `published_at_jst` | 投稿成功時刻 |
| `external_post_id` | SNS側投稿ID |
| `error_message` | 失敗理由 |

### `review_notes`

ユーザーやAI校閲担当の修正メモを残します。

### `settings`

n8n側で参照する設定メモを置きます。APIキーは置きません。

---

## 承認ルール

n8nは以下の条件をすべて満たす行だけ投稿します。

```text
status = approved
fact_check_status = ok
scheduled_at_jst <= 現在JST
published_at_jst が空
```

ユーザーが内容確認してOKする操作は、原則として `status` を `approved` にするだけです。

---

## 媒体別の扱い

### Facebook / Instagram

Meta Graph APIまたはMeta Business Suite連携で自動投稿します。Instagram画像投稿には、公開アクセス可能な画像URLが必要です。

### X

X APIで投稿します。ただし、APIプラン・リンク投稿コスト・文字数制限の確認が必要です。リンク付き投稿は費用や制限の影響を受ける可能性があります。

### Threads

Threads APIまたはMeta公式連携で投稿します。利用可能な権限や投稿形式は実行前に確認してください。

### note

公式の安定した投稿APIが使えない場合、`status=approved` の記事を「手動投稿待ち」として扱います。n8nではSlack/メール/自分宛通知などで下書き内容を送る運用にします。

### LINE

島内向けLINEは、勝手に一斉送信するより「転送文を作る」運用を基本にします。公式LINE配信を使う場合は、既存LINE通知と二重送信にならないよう別管理にします。

---

## 安全設計

- APIキーはn8n credentialsか環境変数で管理する。
- Google Sheetsには投稿本文と予定だけ置く。
- 自動投稿前に事実確認ステータスを必須にする。
- 投稿後はSNS側IDを保存し、二重投稿を防ぐ。
- 失敗時は `error` にして自動再試行しない。
- noteとLINEはまず半自動運用にする。

---

## 初期導入手順

1. Google Sheetsを新規作成する。
2. Apps Scriptに `docs/google_sheets_sns_approval_calendar_apps_script.gs` を貼り付ける。
3. `setupRishiriSnsApprovalCalendar()` を実行する。
4. `docs/SNS_CONTENT_CALENDAR_4WEEK.md` の初回投稿案を `post_queue` に貼り付ける。
5. n8nに `docs/n8n_sns_approval_publishing_blueprint.json` を参考にワークフローを作る。
6. 各SNSの認証情報をn8n credentialsに設定する。
7. 最初は `dry_run=true` でログだけ確認する。
8. 問題なければFacebook/Instagramから自動投稿を開始する。
9. X/Threads/noteはAPI条件を確認して段階的に有効化する。

---

## 推奨運用

最初の1か月は、自動投稿対象を絞ります。

| フェーズ | 自動投稿 | 半自動 |
|---|---|---|
| 1週目 | なし。dry runのみ | 全媒体 |
| 2週目 | Facebookのみ | Instagram/X/Threads/note |
| 3週目 | Facebook + Instagram | X/Threads/note |
| 4週目 | Facebook + Instagram + Threads候補 | X/note |

いきなり全媒体を自動化しないでください。

---

## 島内向け宣伝の終了ルール

利尻島内向けの宣伝投稿・広告は、昆布漁期に合わせて9月末で一旦終了します。

n8n側では、`campaign=rishiri_island` または `audience=island` の投稿について、`scheduled_at_jst` が10月1日以降のものを自動投稿対象から除外してください。

10月以降は以下に切り替えます。

- 島内向け広告配信は停止
- 相談フォームは低頻度で確認
- 干し記録の集計・精度分析
- 次年度改善メモ作成

全国一次産業向けの `campaign=national_primary_industry` は9月以降も継続して構いません。
