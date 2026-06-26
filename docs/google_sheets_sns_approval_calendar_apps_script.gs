/**
 * SNS approval calendar helper for Google Sheets.
 *
 * Usage:
 * 1. Create a Google Sheet for SNS planning.
 * 2. Extensions > Apps Script.
 * 3. Paste this file and run setupRishiriSnsApprovalCalendar().
 *
 * This script only creates tabs, headers, validation, and formatting.
 * It does not post to any SNS.
 */

const SNS_TABS = [
  'post_queue',
  'review_notes',
  'settings',
  'weekly_view'
];

const SNS_COLORS = {
  navy: '#1F3A5F',
  teal: '#0F766E',
  orange: '#ED7D31',
  pale: '#EAF2F8',
  grid: '#D5DEE7',
  text: '#1E293B',
  approved: '#DCFCE7',
  warning: '#FEF3C7',
  error: '#FEE2E2'
};

const POST_QUEUE_HEADERS = [
  'post_id',
  'campaign',
  'audience',
  'platform',
  'post_type',
  'status',
  'fact_check_status',
  'scheduled_at_jst',
  'title',
  'body',
  'cta',
  'url',
  'asset_url',
  'asset_notes',
  'approval_notes',
  'published_at_jst',
  'external_post_id',
  'error_message'
];

function setupRishiriSnsApprovalCalendar() {
  const ss = SpreadsheetApp.getActive();
  ensureSnsTabs_(ss);
  setupPostQueue_(ss);
  setupReviewNotes_(ss);
  setupSettings_(ss);
  setupWeeklyView_(ss);
}

function ensureSnsTabs_(ss) {
  SNS_TABS.forEach(name => {
    if (!ss.getSheetByName(name)) {
      ss.insertSheet(name);
    }
  });
}

function setupPostQueue_(ss) {
  const sheet = ss.getSheetByName('post_queue');
  sheet.clear();
  sheet.getRange(1, 1, 1, POST_QUEUE_HEADERS.length).setValues([POST_QUEUE_HEADERS]);
  styleSnsHeader_(sheet.getRange(1, 1, 1, POST_QUEUE_HEADERS.length));
  sheet.setFrozenRows(1);
  sheet.setFrozenColumns(1);
  sheet.setColumnWidths(1, 1, 150);
  sheet.setColumnWidths(2, 7, 130);
  sheet.setColumnWidths(8, 1, 170);
  sheet.setColumnWidths(9, 1, 220);
  sheet.setColumnWidths(10, 1, 520);
  sheet.setColumnWidths(11, 8, 180);
  sheet.getRange(1, 1, 200, POST_QUEUE_HEADERS.length).setWrap(true);

  applyValidation_(sheet, 2, 2, ['rishiri_island', 'national_primary_industry']);
  applyValidation_(sheet, 2, 3, ['island', 'national']);
  applyValidation_(sheet, 2, 4, ['facebook', 'instagram', 'x', 'threads', 'note', 'line_share']);
  applyValidation_(sheet, 2, 5, ['text', 'image', 'thread', 'article', 'line_text']);
  applyValidation_(sheet, 2, 6, ['draft', 'needs_review', 'approved', 'scheduled', 'published', 'error', 'hold']);
  applyValidation_(sheet, 2, 7, ['unchecked', 'ok', 'needs_fix', 'blocked']);

  const statusRange = sheet.getRange(2, 6, 199, 1);
  const rules = [
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('approved')
      .setBackground(SNS_COLORS.approved)
      .setRanges([statusRange])
      .build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('needs_review')
      .setBackground(SNS_COLORS.warning)
      .setRanges([statusRange])
      .build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextEqualTo('error')
      .setBackground(SNS_COLORS.error)
      .setRanges([statusRange])
      .build()
  ];
  sheet.setConditionalFormatRules(rules);
}

function setupReviewNotes_(ss) {
  const sheet = ss.getSheetByName('review_notes');
  sheet.clear();
  const headers = ['created_at_jst', 'post_id', 'reviewer', 'note_type', 'note', 'resolved'];
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  styleSnsHeader_(sheet.getRange(1, 1, 1, headers.length));
  sheet.setFrozenRows(1);
  sheet.setColumnWidths(1, 6, 160);
  sheet.setColumnWidth(5, 520);
  sheet.getRange(1, 1, 200, headers.length).setWrap(true);
}

function setupSettings_(ss) {
  const sheet = ss.getSheetByName('settings');
  sheet.clear();
  writeSnsTitle_(sheet, 'SNS Approval Settings', 'APIキーはここに保存しない。n8n credentialsで管理する。');
  const rows = [
    ['timezone', 'Asia/Tokyo'],
    ['poll_interval', '15 minutes'],
    ['approval_rule', 'status=approved AND fact_check_status=ok AND scheduled_at_jst<=now AND published_at_jst is blank'],
    ['dry_run_first', 'true'],
    ['facebook', 'Meta Graph API or Meta Business Suite'],
    ['instagram', 'Instagram Graph API; image posts need public asset_url'],
    ['x', 'X API; plan/cost/limits must be checked before enabling'],
    ['threads', 'Threads API/Meta official route; permissions must be checked'],
    ['note', 'manual or semi-automatic draft notification unless stable API is available'],
    ['line_share', 'generate share text; do not mass-send without separate approval']
  ];
  sheet.getRange(4, 1, rows.length, 2).setValues(rows);
  styleSnsHeader_(sheet.getRange(4, 1, 1, 2));
  sheet.setColumnWidths(1, 1, 180);
  sheet.setColumnWidths(2, 1, 760);
  sheet.getRange(4, 1, rows.length, 2).setWrap(true);
}

function setupWeeklyView_(ss) {
  const sheet = ss.getSheetByName('weekly_view');
  sheet.clear();
  writeSnsTitle_(sheet, 'Weekly SNS View', 'post_queueから今後の投稿を確認する簡易ビュー');
  sheet.getRange('A4').setValue('今後の投稿');
  sheet.getRange('A5').setFormula('=SORT(FILTER(post_queue!A:R,post_queue!F:F<>"published",post_queue!F:F<>"error"),8,TRUE)');
  sheet.setFrozenRows(4);
  sheet.setColumnWidths(1, 18, 140);
  sheet.setColumnWidth(10, 520);
}

function applyValidation_(sheet, startRow, col, values) {
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(values, true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(startRow, col, 199, 1).setDataValidation(rule);
}

function writeSnsTitle_(sheet, title, subtitle) {
  sheet.getRange(1, 1, 1, 8).merge().setValue(title);
  sheet.getRange(1, 1, 1, 8)
    .setBackground(SNS_COLORS.navy)
    .setFontColor('#FFFFFF')
    .setFontWeight('bold')
    .setFontSize(14);
  sheet.getRange(2, 1, 1, 8).merge().setValue(subtitle);
  sheet.getRange(2, 1, 1, 8)
    .setBackground(SNS_COLORS.pale)
    .setFontColor('#64748B')
    .setFontSize(10);
}

function styleSnsHeader_(range) {
  range
    .setBackground(SNS_COLORS.teal)
    .setFontColor('#FFFFFF')
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle')
    .setWrap(true)
    .setBorder(true, true, true, true, true, true, SNS_COLORS.grid, SpreadsheetApp.BorderStyle.SOLID);
}

