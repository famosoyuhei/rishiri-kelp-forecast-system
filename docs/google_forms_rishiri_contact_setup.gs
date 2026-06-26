/**
 * Rishiri contact form setup for Google Apps Script.
 *
 * Usage:
 * 1. Create a Google Sheet for contact management.
 * 2. Extensions > Apps Script.
 * 3. Paste this file.
 * 4. Change ADMIN_EMAIL.
 * 5. Run setupRishiriContactForm().
 *
 * The script creates a Google Form, links responses to the current Sheet,
 * adds operation columns, and installs notification triggers.
 */

const ADMIN_EMAIL = 'your-email@example.com';
const APP_NAME = '利尻島昆布干場予報システム';
const FORM_TITLE = '利尻島昆布干場予報 相談フォーム';

function setupRishiriContactForm() {
  const ss = SpreadsheetApp.getActive();
  const form = FormApp.create(FORM_TITLE);

  form.setDescription([
    '利尻島内向けアプリは、2026年9月末まで自由に使える形で公開しています。',
    '相談は任意です。',
    '',
    '使い方がわからない、干場が見つからない、不具合がある、追加してほしい機能がある場合はこちらからお知らせください。',
    '',
    '電話対応は現在行っていません。すぐに返信できない場合がありますが、内容は確認します。',
    '',
    '予報は作業判断の補助情報です。現地の空・風・海の様子とあわせて確認してください。',
    '',
    '予報改善のため、干せた日・干せなかった日の記録入力にもご協力いただけると助かります。入力は任意で、わかる範囲でかまいません。'
  ].join('\n'));

  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setLimitOneResponsePerUser(false);
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  form.addTextItem()
    .setTitle('お名前、または呼び名')
    .setHelpText('本名でなくてもかまいません。')
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('関係')
    .setChoiceValues(['昆布漁師', '家族・手伝い', '漁協・地域関係', 'その他'])
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('地区')
    .setChoiceValues(['沓形', '仙法志', '鴛泊', '鬼脇', 'その他'])
    .setRequired(false);

  form.addCheckboxItem()
    .setTitle('相談内容')
    .setChoiceValues(['使い方', '干場が見つからない', '不具合', '機能の希望', '干し記録について', 'その他'])
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('詳しい内容')
    .setHelpText('困っていること、見つからない干場、表示されたエラーなどをわかる範囲で書いてください。')
    .setRequired(true);

  form.addTextItem()
    .setTitle('返信先メール')
    .setHelpText('返信が必要な場合だけ入力してください。電話番号は不要です。')
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('返信希望')
    .setChoiceValues(['返信不要', '急ぎではない', 'できれば数日以内'])
    .setRequired(true);

  Utilities.sleep(1500);
  const responseSheet = findResponseSheet_(ss);
  ensureOpsColumns_(responseSheet);
  styleContactSheet_(responseSheet);
  installContactTriggers_(ss);

  const setup = getOrCreateSheet_(ss, 'contact_setup');
  setup.clear();
  setup.getRange(1, 1, 1, 2).setValues([['項目', '内容']]);
  setup.getRange(2, 1, 7, 2).setValues([
    ['フォーム編集URL', form.getEditUrl()],
    ['フォーム公開URL', form.getPublishedUrl()],
    ['LP差し替え箇所', 'rishiri_island_lp.html の CONSULT_FORM_URL'],
    ['管理者メール', ADMIN_EMAIL],
    ['回答シート', responseSheet.getName()],
    ['島内宣伝終了', '9月末で一旦終了'],
    ['全国向け発信', '9月以降も継続']
  ]);
  setup.setFrozenRows(1);
  setup.autoResizeColumns(1, 2);

  Logger.log('Form edit URL: ' + form.getEditUrl());
  Logger.log('Form public URL: ' + form.getPublishedUrl());
}

function onContactFormSubmit(e) {
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
  const sheet = findResponseSheet_(ss);
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

function installContactTriggers_(ss) {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => {
    const handler = trigger.getHandlerFunction();
    if (handler === 'onContactFormSubmit' || handler === 'sendDailyOpenItemsSummary') {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  ScriptApp.newTrigger('onContactFormSubmit')
    .forSpreadsheet(ss)
    .onFormSubmit()
    .create();

  ScriptApp.newTrigger('sendDailyOpenItemsSummary')
    .timeBased()
    .everyDays(1)
    .atHour(9)
    .create();
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

function findResponseSheet_(ss) {
  const sheets = ss.getSheets();
  return sheets.find(sheet => sheet.getName().includes('フォームの回答')) || sheets[0];
}

function getOrCreateSheet_(ss, name) {
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function styleContactSheet_(sheet) {
  const lastCol = sheet.getLastColumn();
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, lastCol)
    .setBackground('#0F766E')
    .setFontColor('#FFFFFF')
    .setFontWeight('bold')
    .setWrap(true);
  sheet.getRange(1, 1, Math.max(sheet.getMaxRows(), 20), lastCol).setWrap(true);
  sheet.autoResizeColumns(1, lastCol);
}

function getFirst_(namedValues, key) {
  const value = namedValues[key];
  if (Array.isArray(value)) return value.join(', ');
  return value || '';
}
