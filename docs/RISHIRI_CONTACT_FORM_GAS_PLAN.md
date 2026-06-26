# 利尻島内向け 相談フォーム + GAS運用設計

## 目的

利尻島内の昆布関係者が、電話なしで気軽に任意相談できる窓口を作る。

海外滞在中や体調都合がある場合でも、Googleフォーム・Google Sheets・GAS通知で非同期に対応できるようにする。

---

## 基本方針

- 電話番号は掲載しない。
- 島内向けアプリは2026年9月末まで自由使用とし、相談は任意にする。
- 相談はGoogleフォームで受ける。
- 回答はGoogle Sheetsに蓄積する。
- GASで自分宛にメール通知する。
- 返信先メールがある場合だけ、自動受付メールを送る。
- 対応状況はSheets上で管理する。
- 島内向け宣伝は昆布漁期に合わせ、9月末で一旦終了する。
- 全国一次産業向けの発信・導入支援は9月以降も継続する。

---

## LPに載せる相談文

```text
使い方がわからない、干場が見つからない、不具合がある、追加してほしい機能がある場合は、フォームからお知らせください。

アプリはそのまま自由に使えます。相談は任意です。

電話対応は現在行っていません。
すぐに返信できない場合がありますが、内容は確認します。

お問い合わせ内容は、アプリ改善と返信のためにのみ使用します。
```

---

## LPに載せる干し記録協力依頼

```text
予報の精度を上げるために、実際に干せた日・干せなかった日の記録入力にご協力ください。

記録が増えるほど、干場ごとの予報の見直しや改善に役立ちます。
入力は任意です。わかる範囲でかまいません。
```

短い版:

```text
予報改善のため、干せた日・干せなかった日の記録入力にご協力ください。任意入力で、わかる範囲で大丈夫です。
```

---

## Googleフォーム項目

| 項目 | 種類 | 必須 | 補足 |
|---|---|---:|---|
| お名前、または呼び名 | 短文 | 任意 | 本名でなくてよい |
| 関係 | ラジオボタン | 任意 | 昆布漁師 / 家族・手伝い / 漁協・地域関係 / その他（自由入力欄なし） |
| 地区 | ラジオボタン | 任意 | 沓形 / 仙法志 / 鴛泊 / 鬼脇 / その他（自由入力欄なし） |
| 相談内容 | チェックボックス | 必須 | 使い方 / 干場が見つからない / 不具合 / 機能の希望 / 干し記録について / その他（自由入力欄なし） |
| 詳しい内容 | 段落 | 必須 | 自由記述 |
| 返信先メール | 短文 | 任意 | 電話番号は不要 |
| 返信希望 | ラジオボタン | 必須 | 返信不要 / 急ぎではない / できれば数日以内 |

---

## Google Sheets追加列

フォーム回答シートの右側に以下の列を追加する。

| 列 | 値 |
|---|---|
| `status` | 未対応 / 確認中 / 返信済み / 対応不要 |
| `priority` | 高 / 中 / 低 |
| `owner_note` | 対応メモ |
| `replied_at` | 返信日時 |

優先度の目安:

- 高: 不具合、干場が見つからない
- 中: 使い方、干し記録について
- 低: 機能の希望、その他

---

## GASコード

フォームの作成から自動化したい場合は、`docs/google_forms_rishiri_contact_setup.gs` を使う。
手動でフォームを作る場合は、以下のコードをフォーム回答先のGoogle Sheetsで使う。

Googleフォーム回答先のGoogle Sheetsで、Apps Scriptに貼り付ける。

`ADMIN_EMAIL` は自分のメールアドレスに変更する。

```javascript
const ADMIN_EMAIL = 'your-email@example.com';
const APP_NAME = '利尻島昆布干場予報システム';

function onFormSubmit(e) {
  const sheet = e.range.getSheet();
  const row = e.range.getRow();
  const values = e.namedValues || {};

  ensureOpsColumns_(sheet);

  const issueType = getFirst_(values, '相談内容');
  const replyEmail = getFirst_(values, '返信先メール');
  const replyPreference = getFirst_(values, '返信希望');
  const detail = getFirst_(values, '詳しい内容');
  const district = getFirst_(values, '地区');
  const relation = getFirst_(values, '関係');
  const name = getFirst_(values, 'お名前、または呼び名');

  const priority = classifyPriority_(issueType);
  setOpsValues_(sheet, row, priority);

  const subject = `【${APP_NAME}】相談フォーム: ${issueType || '内容未分類'} / ${priority}`;
  const body = [
    `${APP_NAME} の相談フォームに回答がありました。`,
    '',
    `優先度: ${priority}`,
    `名前/呼び名: ${name || '未入力'}`,
    `関係: ${relation || '未入力'}`,
    `地区: ${district || '未入力'}`,
    `相談内容: ${issueType || '未入力'}`,
    `返信希望: ${replyPreference || '未入力'}`,
    `返信先メール: ${replyEmail || '未入力'}`,
    '',
    '詳しい内容:',
    detail || '未入力',
    '',
    `シート: ${SpreadsheetApp.getActive().getUrl()}`
  ].join('\n');

  MailApp.sendEmail(ADMIN_EMAIL, subject, body);

  if (replyEmail && replyPreference !== '返信不要') {
    sendAutoReply_(replyEmail, name);
  }
}

function sendDailyOpenItemsSummary() {
  const ss = SpreadsheetApp.getActive();
  const sheet = ss.getSheets()[0];
  ensureOpsColumns_(sheet);

  const values = sheet.getDataRange().getValues();
  const headers = values[0];
  const statusCol = headers.indexOf('status');
  const priorityCol = headers.indexOf('priority');
  const openRows = values.slice(1).filter(row => {
    const status = row[statusCol];
    return !status || status === '未対応' || status === '確認中';
  });

  if (openRows.length === 0) return;

  const highCount = openRows.filter(row => row[priorityCol] === '高').length;
  const subject = `【${APP_NAME}】未対応相談 ${openRows.length}件（高 ${highCount}件）`;
  const body = [
    `未対応または確認中の相談が ${openRows.length} 件あります。`,
    `高優先度: ${highCount} 件`,
    '',
    SpreadsheetApp.getActive().getUrl()
  ].join('\n');

  MailApp.sendEmail(ADMIN_EMAIL, subject, body);
}

function ensureOpsColumns_(sheet) {
  const required = ['status', 'priority', 'owner_note', 'replied_at'];
  const lastCol = sheet.getLastColumn();
  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  let appendAt = lastCol + 1;

  required.forEach(name => {
    if (!headers.includes(name)) {
      sheet.getRange(1, appendAt).setValue(name);
      appendAt += 1;
    }
  });
}

function setOpsValues_(sheet, row, priority) {
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const statusCol = headers.indexOf('status') + 1;
  const priorityCol = headers.indexOf('priority') + 1;

  if (statusCol > 0 && !sheet.getRange(row, statusCol).getValue()) {
    sheet.getRange(row, statusCol).setValue('未対応');
  }
  if (priorityCol > 0) {
    sheet.getRange(row, priorityCol).setValue(priority);
  }
}

function classifyPriority_(issueType) {
  const text = String(issueType || '');
  if (text.includes('不具合') || text.includes('干場が見つからない')) return '高';
  if (text.includes('使い方') || text.includes('干し記録')) return '中';
  return '低';
}

function sendAutoReply_(email, name) {
  const displayName = name ? `${name} 様` : 'お問い合わせいただいた方へ';
  const subject = `【${APP_NAME}】お問い合わせを受け付けました`;
  const body = [
    displayName,
    '',
    `${APP_NAME} へのお問い合わせを受け付けました。`,
    'すぐに返信できない場合がありますが、内容を確認します。',
    '',
    '電話対応は現在行っていません。',
    '予報は作業判断の補助情報として、現地の空・風・海の様子とあわせて確認してください。',
    '',
    'また、予報改善のため、干せた日・干せなかった日の記録入力にもご協力いただけると助かります。',
    '入力は任意で、わかる範囲でかまいません。'
  ].join('\n');

  MailApp.sendEmail(email, subject, body);
}

function getFirst_(namedValues, key) {
  const value = namedValues[key];
  if (Array.isArray(value)) return value.join(', ');
  return value || '';
}
```

---

## トリガー設定

Apps Scriptで以下を設定する。

| 関数 | トリガー | 頻度 |
|---|---|---|
| `onFormSubmit` | フォーム送信時 | 毎回 |
| `sendDailyOpenItemsSummary` | 時間主導型 | 毎朝 9:00 JST |

---

## 島内向け宣伝の終了ルール

島内向けのSNS広告・投稿強化・LP告知は、昆布漁期に合わせて9月末で一旦終了する。

10月以降:

- 新規広告配信は停止
- LPは必要なら残す
- 相談フォームは低頻度で確認
- 干し記録の集計・精度分析に移る
- 次年度に向けた改善点を整理する

全国向けの一次産業導入支援は、9月以降も継続してよい。
