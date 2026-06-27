/**
 * National primary-industry consultation form setup for Google Apps Script.
 *
 * Usage:
 * 1. Create a new Google Sheet for national consultation management.
 * 2. Extensions > Apps Script.
 * 3. Paste this file.
 * 4. Change ADMIN_EMAIL.
 * 5. Run setupNationalIndustryContactForm().
 *
 * The script creates a Google Form, links responses to the current Sheet,
 * adds operation columns, and installs notification triggers.
 *
 * Note:
 * This script intentionally does not use showOtherOption(true).
 * "その他" appears only as a normal option, and details are collected in
 * paragraph fields so Google Forms does not create duplicate Other fields.
 */

const ADMIN_EMAIL = 'your-email@example.com';
const SERVICE_NAME = '一次産業向け 天候判断アプリ導入支援';
const FORM_TITLE = '一次産業向け 天候判断アプリ導入相談フォーム';
const DEMO_URL = 'https://rishiri-kelp-forecast-system.onrender.com/island';

function setupNationalIndustryContactForm() {
  const ss = SpreadsheetApp.getActive();
  const form = FormApp.create(FORM_TITLE);

  form.setDescription([
    '天候で作業判断や収支が変わる一次産業向けに、地域・業種・作業内容に合わせた専用アプリの導入相談を受け付けています。',
    '',
    '利尻島の昆布干場予報アプリは構築例です。',
    '全国向けには、そのまま使うのではなく、現場ごとの作業判断・地点・通知先・記録項目に合わせて個別に設計します。',
    '',
    `構築例: ${DEMO_URL}`,
    '',
    'このフォームの送信、内容確認、メールでの簡単な初回回答までは無料です。',
    '個別ヒアリング、要件整理、試作、構築、運用支援などが必要になった場合は、希望する関わり方と内容を確認したうえで事前に相談します。',
    '勝手に有料作業へ進むことはありません。',
    '',
    '相談・ヒアリング前提です。まだ具体化していない段階でも、わかる範囲で入力してください。',
    '',
    '予報やスコアは作業判断の補助情報です。最終判断は現地の状況や既存の安全基準とあわせて行う前提です。'
  ].join('\n'));

  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setLimitOneResponsePerUser(false);
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  form.addSectionHeaderItem()
    .setTitle('無料範囲と有料相談について')
    .setHelpText([
      '無料: フォーム送信、内容確認、メールでの簡単な初回回答、構築例の閲覧。',
      '有料になり得るもの: 個別ヒアリング、要件整理、試作、アプリ構築、通知設定、記録・精度分析の仕組み作り、運用支援。',
      '支援スタイルは、伴走型、完成コード納品型、最初だけ使い方を教える自走型など、希望に合わせて相談できます。',
      '費用が発生する場合は、作業前に内容と進め方を確認します。フォーム送信だけで料金は発生しません。'
    ].join('\n'));

  form.addTextItem()
    .setTitle('お名前')
    .setRequired(false);

  form.addTextItem()
    .setTitle('法人名・屋号')
    .setHelpText('差し支えなければ入力してください。個人での相談の場合は未入力でもかまいません。')
    .setRequired(false);

  form.addTextItem()
    .setTitle('返信先メール')
    .setHelpText('必須です。まずはメールで返信します。通話ツールや詳しい相談方法は、初回返信後に確認します。')
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('業種')
    .setChoiceValues([
      '牧草・酪農',
      '露地野菜',
      '果樹',
      '米・畑作',
      '水産・沿岸漁業',
      '養殖',
      '農作業受託・ドローン散布',
      '自治体・支援機関',
      'その他'
    ])
    .setRequired(false);

  form.addTextItem()
    .setTitle('地域')
    .setHelpText('都道府県・市町村など、差し支えない範囲で入力してください。')
    .setRequired(false);

  form.addCheckboxItem()
    .setTitle('天候で迷う作業判断')
    .setChoiceValues([
      '刈取',
      '乾燥',
      '防除',
      '収穫',
      '定植・播種',
      '出漁・沿岸作業',
      '給餌・網管理',
      '霜害・高温対策',
      'ドローン散布',
      'その他'
    ])
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle('具体的に困っている判断')
    .setHelpText('例: 牧草を刈る日、雨前のロール判断、防除に入れる風か、強風時に出漁するか、など。')
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('見たい地点数の目安')
    .setChoiceValues([
      '1地点',
      '2〜5地点',
      '6〜20地点',
      '21〜100地点',
      '100地点以上',
      'まだわからない'
    ])
    .setRequired(false);

  form.addCheckboxItem()
    .setTitle('必要そうな機能')
    .setChoiceValues([
      '地点ごとの予報',
      '作業可否スコア',
      '地図表示',
      'LINE通知',
      'メール通知',
      '作業記録',
      'Google Sheetsで精度分析',
      '管理者向け画面',
      'まだわからない'
    ])
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('希望する支援スタイル')
    .setHelpText('まだ決まっていない場合は、近いものを選んでください。あとで変更できます。')
    .setChoiceValues([
      '伴走型: 相談しながら構築・運用まで継続的に見てほしい',
      '丸投げ型: 要望を伝えて、使える状態まで任せたい',
      'コード納品型: 完成したコードだけ受け取り、自分で設置・運用したい',
      '自走支援型: Claude CodeやCodex等の使い方を最初だけ教わり、あとは自分で進めたい',
      'まだわからない'
    ])
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle('現在使っている天気情報・判断方法')
    .setHelpText('天気アプリ、気象庁、Windy、経験判断、観測機器など。未入力でもかまいません。')
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle('相談したい内容')
    .setHelpText('実現できるか知りたいこと、予算感、試験運用の希望、既存データの有無など。')
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('相談希望')
    .setChoiceValues([
      'まずメールで相談したい',
      'オンライン打ち合わせを相談したい',
      '資料や例を見てから考えたい',
      'まだ情報収集段階'
    ])
    .setRequired(false);

  form.addCheckboxItem()
    .setTitle('希望する連絡・打ち合わせ手段')
    .setHelpText('電話番号での通話対応は基本的に行いません。使えるものを選んでください。複数選択できます。')
    .setChoiceValues([
      'WhatsApp',
      'Zoom',
      'Google Meet',
      'LINE',
      'Skype',
      'メール',
      'チャット・文字でのやり取りのみ',
      '電話以外は使えない',
      'まだわからない'
    ])
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle('連絡手段に関する補足')
    .setHelpText('WhatsApp、LINE、Skype等のIDをすぐ書きたくない場合は空欄でかまいません。初回返信後に確認します。')
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('構築例の確認')
    .setChoiceValues([
      '利尻島の構築例を見た',
      'これから見る',
      'まだ見ていない'
    ])
    .setRequired(false);

  Utilities.sleep(1500);
  const responseSheet = findResponseSheet_(ss);
  ensureNationalOpsColumns_(responseSheet);
  styleNationalContactSheet_(responseSheet);
  installNationalContactTriggers_(ss);

  const setup = getOrCreateSheet_(ss, 'national_contact_setup');
  setup.clear();
  setup.getRange(1, 1, 1, 2).setValues([['項目', '内容']]);
  setup.getRange(2, 1, 8, 2).setValues([
    ['フォーム編集URL', form.getEditUrl()],
    ['フォーム公開URL', form.getPublishedUrl()],
    ['構築例URL', DEMO_URL],
    ['管理者メール', ADMIN_EMAIL],
    ['回答シート', responseSheet.getName()],
    ['用途', '全国一次産業向け導入相談'],
    ['注意', '利尻島内向け無料利用フォームとは分けて運用'],
    ['その他欄', 'showOtherOption(true)は使用しない']
  ]);
  setup.setFrozenRows(1);
  setup.autoResizeColumns(1, 2);

  Logger.log('Form edit URL: ' + form.getEditUrl());
  Logger.log('Form public URL: ' + form.getPublishedUrl());
}

function onNationalIndustryFormSubmit(e) {
  const sheet = e.range.getSheet();
  const row = e.range.getRow();
  const values = e.namedValues || {};

  ensureNationalOpsColumns_(sheet);

  const name = getFirst_(values, 'お名前');
  const company = getFirst_(values, '法人名・屋号');
  const email = getFirst_(values, '返信先メール');
  const industry = getFirst_(values, '業種');
  const region = getFirst_(values, '地域');
  const decisions = getFirst_(values, '天候で迷う作業判断');
  const detail = getFirst_(values, '具体的に困っている判断');
  const spotCount = getFirst_(values, '見たい地点数の目安');
  const features = getFirst_(values, '必要そうな機能');
  const supportStyle = getFirst_(values, '希望する支援スタイル');
  const currentMethod = getFirst_(values, '現在使っている天気情報・判断方法');
  const consultation = getFirst_(values, '相談したい内容');
  const preference = getFirst_(values, '相談希望');
  const contactMethods = getFirst_(values, '希望する連絡・打ち合わせ手段');
  const contactNote = getFirst_(values, '連絡手段に関する補足');
  const demoStatus = getFirst_(values, '構築例の確認');

  const priority = classifyNationalPriority_(spotCount, preference, detail);
  setNationalOpsValues_(sheet, row, priority);

  const subject = `【${SERVICE_NAME}】導入相談: ${industry || '業種未入力'} / ${priority}`;
  const body = [
    `${SERVICE_NAME} の相談フォームに回答がありました。`,
    '',
    `優先度: ${priority}`,
    `名前: ${name || '未入力'}`,
    `法人名・屋号: ${company || '未入力'}`,
    `返信先メール: ${email || '未入力'}`,
    `業種: ${industry || '未入力'}`,
    `地域: ${region || '未入力'}`,
    `天候で迷う作業判断: ${decisions || '未入力'}`,
    `見たい地点数: ${spotCount || '未入力'}`,
    `必要そうな機能: ${features || '未入力'}`,
    `希望する支援スタイル: ${supportStyle || '未入力'}`,
    `相談希望: ${preference || '未入力'}`,
    `希望する連絡・打ち合わせ手段: ${contactMethods || '未入力'}`,
    `構築例の確認: ${demoStatus || '未入力'}`,
    '',
    '具体的に困っている判断:',
    detail || '未入力',
    '',
    '現在使っている天気情報・判断方法:',
    currentMethod || '未入力',
    '',
    '相談したい内容:',
    consultation || '未入力',
    '',
    '連絡手段に関する補足:',
    contactNote || '未入力',
    '',
    `構築例: ${DEMO_URL}`,
    `シート: ${SpreadsheetApp.getActive().getUrl()}`
  ].join('\n');

  MailApp.sendEmail(ADMIN_EMAIL, subject, body);

  if (email) {
    sendNationalAutoReply_(email, name, company);
  }
}

function sendDailyNationalOpenItemsSummary() {
  const ss = SpreadsheetApp.getActive();
  const sheet = findResponseSheet_(ss);
  ensureNationalOpsColumns_(sheet);

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
  const subject = `【${SERVICE_NAME}】未対応相談 ${openRows.length}件（高 ${highCount}件）`;
  const body = [
    `未対応または確認中の全国向け導入相談が ${openRows.length} 件あります。`,
    `高優先度: ${highCount} 件`,
    '',
    SpreadsheetApp.getActive().getUrl()
  ].join('\n');

  MailApp.sendEmail(ADMIN_EMAIL, subject, body);
}

function installNationalContactTriggers_(ss) {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => {
    const handler = trigger.getHandlerFunction();
    if (handler === 'onNationalIndustryFormSubmit' || handler === 'sendDailyNationalOpenItemsSummary') {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  ScriptApp.newTrigger('onNationalIndustryFormSubmit')
    .forSpreadsheet(ss)
    .onFormSubmit()
    .create();

  ScriptApp.newTrigger('sendDailyNationalOpenItemsSummary')
    .timeBased()
    .everyDays(1)
    .atHour(9)
    .create();
}

function ensureNationalOpsColumns_(sheet) {
  const required = ['status', 'priority', 'owner_note', 'next_action', 'replied_at'];
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

function setNationalOpsValues_(sheet, row, priority) {
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  const statusCol = headers.indexOf('status') + 1;
  const priorityCol = headers.indexOf('priority') + 1;
  const nextActionCol = headers.indexOf('next_action') + 1;

  if (statusCol > 0 && !sheet.getRange(row, statusCol).getValue()) {
    sheet.getRange(row, statusCol).setValue('未対応');
  }
  if (priorityCol > 0) {
    sheet.getRange(row, priorityCol).setValue(priority);
  }
  if (nextActionCol > 0 && !sheet.getRange(row, nextActionCol).getValue()) {
    sheet.getRange(row, nextActionCol).setValue('初回返信');
  }
}

function classifyNationalPriority_(spotCount, preference, detail) {
  const combined = `${spotCount || ''} ${preference || ''} ${detail || ''}`;
  if (combined.includes('オンライン打ち合わせ') || combined.includes('100地点以上') || combined.includes('21〜100地点')) {
    return '高';
  }
  if (combined.includes('まずメール') || combined.includes('6〜20地点')) {
    return '中';
  }
  return '低';
}

function sendNationalAutoReply_(email, name, company) {
  const displayName = name ? `${name} 様` : 'お問い合わせいただいた方へ';
  const subject = `【${SERVICE_NAME}】導入相談を受け付けました`;
  const body = [
    displayName,
    '',
    `${SERVICE_NAME} への導入相談を受け付けました。`,
    company ? `法人名・屋号: ${company}` : '',
    '',
    '全国向けの導入支援は、業種・地域・地点・作業判断が現場ごとに違うため、相談とヒアリングを前提にしています。',
    '伴走型、丸投げ型、コード納品型、自走支援型など、希望する関わり方に合わせて進め方を相談します。',
    '打ち合わせが必要な場合は、WhatsApp、Zoom、Google Meet、LINE、Skype、メール、文字でのやり取りなど、使える手段に合わせて相談します。',
    '電話番号での通話対応は基本的に行っていません。',
    '希望する通話ツールや連絡方法があれば、このメールへの返信で教えてください。',
    '入力内容を確認し、必要に応じて追加で確認したい点をメールでご連絡します。',
    '',
    '構築例として、利尻島の昆布干場予報アプリを公開しています。',
    DEMO_URL,
    '',
    '予報やスコアは作業判断の補助情報です。最終判断は現地の状況や既存の安全基準とあわせて行う前提です。'
  ].filter(Boolean).join('\n');

  MailApp.sendEmail(email, subject, body);
}

function findResponseSheet_(ss) {
  const sheets = ss.getSheets();
  return sheets.find(sheet => sheet.getName().includes('フォームの回答')) || sheets[0];
}

function getOrCreateSheet_(ss, name) {
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function styleNationalContactSheet_(sheet) {
  const lastCol = sheet.getLastColumn();
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, lastCol)
    .setBackground('#1D4ED8')
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
