/**
 * Rishiri kelp forecast accuracy dashboard helper for Google Sheets.
 *
 * Usage:
 * 1. Create or open the Google Sheet used by n8n.
 * 2. Extensions > Apps Script.
 * 3. Paste this file and run setupRishiriAccuracyDashboard().
 *
 * This script only formats Sheets tabs and creates charts. It does not call
 * the Flask app, LINE, Open-Meteo, or n8n.
 */

const RISHIRI_TABS = [
  'Dashboard',
  'spot_master',
  'spot_detail',
  'raw_feedback',
  'summary_by_day',
  'summary_by_days_ahead',
  'summary_by_area',
  'summary_by_buraku',
  'n8n_setup'
];

const RISHIRI_COLORS = {
  navy: '#1F3A5F',
  teal: '#0F766E',
  blue: '#1F77B4',
  orange: '#ED7D31',
  pale: '#EAF2F8',
  grid: '#D5DEE7',
  text: '#1E293B'
};

function setupRishiriAccuracyDashboard() {
  const ss = SpreadsheetApp.getActive();
  ensureTabs_(ss);
  setupN8nSetupTab_(ss);
  formatDataTabs_(ss);
  setupSpotDetail_(ss);
  setupDashboard_(ss);
}

function ensureTabs_(ss) {
  RISHIRI_TABS.forEach(name => {
    if (!ss.getSheetByName(name)) {
      ss.insertSheet(name);
    }
  });
}

function setupN8nSetupTab_(ss) {
  const sheet = ss.getSheetByName('n8n_setup');
  sheet.clear();
  writeTitle_(sheet, 'n8n Setup', 'Google Sheets同期用の設定メモ');
  const rows = [
    ['Raw API', 'https://rishiri-kelp-forecast-system.onrender.com/api/validation/accuracy/sheets?days=90'],
    ['Summary API', 'https://rishiri-kelp-forecast-system.onrender.com/api/validation/accuracy/sheets/summary?days=90'],
    ['Spot master API', 'https://rishiri-kelp-forecast-system.onrender.com/api/integration/spots/sheets'],
    ['Raw tab', 'raw_feedback'],
    ['Summary tabs', 'summary_by_day, summary_by_days_ahead, summary_by_area, summary_by_buraku'],
    ['Raw Matching Column', 'upsert_key'],
    ['Summary Matching Column', 'summary_key'],
    ['Schedule', '毎日 03:35 JST以降'],
    ['HTTP Request', 'Response Format: JSON'],
    ['Google Sheets', 'Append or Update Row'],
    ['注意', '/api/forecast を全地点へ連打しない']
  ];
  sheet.getRange(4, 1, rows.length, 2).setValues(rows);
  styleHeader_(sheet.getRange(4, 1, 1, 2));
  styleBody_(sheet.getRange(5, 1, rows.length - 1, 2));
  sheet.setColumnWidths(1, 1, 170);
  sheet.setColumnWidths(2, 1, 650);
  sheet.getRange(4, 1, rows.length, 2).setWrap(true);
}

function formatDataTabs_(ss) {
  const spotMaster = ss.getSheetByName('spot_master');
  ensureHeader_(spotMaster, [
    'master_key', 'spot_name', 'spot_type', 'is_active', 'is_protected',
    'lat', 'lon', 'town', 'district', 'buraku', 'synced_at_jst'
  ]);

  const raw = ss.getSheetByName('raw_feedback');
  const rawHeaders = [
    'upsert_key', 'date', 'spot_name', 'town', 'district', 'buraku', 'days_ahead',
    'actual_precip_0416_mm', 'actual_precip_total_mm', 'actual_rain_0416',
    'forecast_precip_mm', 'forecast_rain', 'precip_forecast_correct',
    'forecast_score', 'forecast_suitability', 'forecast_label',
    'actual_result', 'actual_label', 'judgment_correct',
    'has_drying_record', 'data_source', 'recorded_at'
  ];
  ensureHeader_(raw, rawHeaders);

  const summaries = {
    summary_by_day: ['date', 'summary_key', 'rows', 'drying_record_rows', 'precip_hit_rate_pct', 'judgment_hit_rate_pct', 'avg_forecast_score', 'false_positive_count', 'false_negative_count'],
    summary_by_days_ahead: ['days_ahead', 'summary_key', 'rows', 'drying_record_rows', 'precip_hit_rate_pct', 'judgment_hit_rate_pct', 'avg_forecast_score', 'false_positive_count', 'false_negative_count'],
    summary_by_area: ['town', 'district', 'summary_key', 'rows', 'drying_record_rows', 'precip_hit_rate_pct', 'judgment_hit_rate_pct', 'avg_forecast_score', 'false_positive_count', 'false_negative_count'],
    summary_by_buraku: ['town', 'district', 'buraku', 'summary_key', 'rows', 'drying_record_rows', 'precip_hit_rate_pct', 'judgment_hit_rate_pct', 'avg_forecast_score', 'false_positive_count', 'false_negative_count']
  };

  Object.entries(summaries).forEach(([name, headers]) => {
    ensureHeader_(ss.getSheetByName(name), headers);
  });
}

function setupSpotDetail_(ss) {
  const sheet = ss.getSheetByName('spot_detail');
  sheet.clear();
  writeTitle_(sheet, '干場別 精度詳細', '1枚のシートで全干場を切り替えて表示');
  sheet.getRange('A4').setValue('干場を選択');
  sheet.getRange('A4').setFontWeight('bold').setBackground(RISHIRI_COLORS.pale);
  sheet.getRange('B4').setDataValidation(
    SpreadsheetApp.newDataValidation()
      .requireValueInRange(ss.getSheetByName('spot_master').getRange('B2:B'), true)
      .setAllowInvalid(false)
      .build()
  );
  sheet.getRange('A6').setValue('選択した干場の履歴');
  sheet.getRange('A6').setFontWeight('bold').setFontColor(RISHIRI_COLORS.navy);
  sheet.getRange('A7').setFormula('=IF($B$4="","",FILTER(raw_feedback!A:V,raw_feedback!C:C=$B$4))');
  sheet.setFrozenRows(6);
  sheet.setColumnWidths(1, 22, 120);
}

function setupDashboard_(ss) {
  const sheet = ss.getSheetByName('Dashboard');
  sheet.clear();
  writeTitle_(sheet, '利尻島昆布干場 予報精度ダッシュボード', 'n8n + Google Sheets 第1段階');

  const kpis = [['対象', 'Raw行数', '乾燥記録行', '降水的中率', '乾燥判定的中率', '平均スコア', 'False Positive', 'False Negative']];
  sheet.getRange(4, 1, 1, kpis[0].length).setValues(kpis);
  sheet.getRange(5, 1, 1, kpis[0].length).setValues([[
    '全体',
    '=COUNTA(raw_feedback!A2:A)',
    '=SUM(summary_by_day!D2:D)',
    '=IFERROR(AVERAGE(summary_by_day!E2:E),"")',
    '=IFERROR(AVERAGE(summary_by_day!F2:F),"")',
    '=IFERROR(AVERAGE(summary_by_day!G2:G),"")',
    '=SUM(summary_by_day!H2:H)',
    '=SUM(summary_by_day!I2:I)'
  ]]);
  styleHeader_(sheet.getRange(4, 1, 1, 8));
  styleBody_(sheet.getRange(5, 1, 1, 8));

  sheet.getRange(8, 1, 7, 2).setValues([
    ['主要グラフ', '元データ'],
    ['日別 的中率推移', 'summary_by_day'],
    ['何日前予報別 精度', 'summary_by_days_ahead'],
    ['地区別 外れ方', 'summary_by_area'],
    ['部落別ランキング', 'summary_by_buraku'],
    ['Rawログ監査', 'raw_feedback'],
    ['干場別詳細', 'spot_detail']
  ]);
  styleHeader_(sheet.getRange(8, 1, 1, 2));
  styleBody_(sheet.getRange(9, 1, 6, 2));

  sheet.getCharts().forEach(chart => sheet.removeChart(chart));

  const byDay = ss.getSheetByName('summary_by_day');
  const byAhead = ss.getSheetByName('summary_by_days_ahead');

  if (byDay.getLastRow() >= 2) {
    const chart = sheet.newChart()
      .asLineChart()
      .addRange(byDay.getRange(1, 1, byDay.getLastRow(), 1))
      .addRange(byDay.getRange(1, 5, byDay.getLastRow(), 2))
      .setPosition(8, 4, 0, 0)
      .setOption('title', '日別 的中率推移')
      .setOption('vAxis', { minValue: 0, maxValue: 100 })
      .setOption('legend', { position: 'bottom' })
      .build();
    sheet.insertChart(chart);
  }

  if (byAhead.getLastRow() >= 2) {
    const chart = sheet.newChart()
      .asColumnChart()
      .addRange(byAhead.getRange(1, 1, byAhead.getLastRow(), 1))
      .addRange(byAhead.getRange(1, 5, byAhead.getLastRow(), 2))
      .setPosition(25, 4, 0, 0)
      .setOption('title', '何日前予報別 精度')
      .setOption('vAxis', { minValue: 0, maxValue: 100 })
      .setOption('legend', { position: 'bottom' })
      .build();
    sheet.insertChart(chart);
  }

  sheet.setColumnWidths(1, 8, 135);
}

function ensureHeader_(sheet, headers) {
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  } else {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }
  styleHeader_(sheet.getRange(1, 1, 1, headers.length));
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, headers.length);
}

function writeTitle_(sheet, title, subtitle) {
  sheet.getRange(1, 1, 1, 8).merge().setValue(title);
  sheet.getRange(1, 1, 1, 8)
    .setBackground(RISHIRI_COLORS.navy)
    .setFontColor('#FFFFFF')
    .setFontWeight('bold')
    .setFontSize(14);
  sheet.getRange(2, 1, 1, 8).merge().setValue(subtitle);
  sheet.getRange(2, 1, 1, 8)
    .setBackground(RISHIRI_COLORS.pale)
    .setFontColor('#64748B')
    .setFontSize(10);
  sheet.setRowHeight(1, 32);
}

function styleHeader_(range) {
  range
    .setBackground(RISHIRI_COLORS.teal)
    .setFontColor('#FFFFFF')
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle')
    .setWrap(true)
    .setBorder(true, true, true, true, true, true, RISHIRI_COLORS.grid, SpreadsheetApp.BorderStyle.SOLID);
}

function styleBody_(range) {
  range
    .setVerticalAlignment('middle')
    .setBorder(true, true, true, true, true, true, RISHIRI_COLORS.grid, SpreadsheetApp.BorderStyle.SOLID);
}
