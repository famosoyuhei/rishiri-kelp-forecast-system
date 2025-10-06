// 統合海洋予報の表示機能
// kelp_drying_map.html の <script> セクションに追加

async function loadOceanIntegratedForecast() {
    try {
        const response = await fetch('/api/viable_drying_hours');
        if (!response.ok) {
            throw new Error('Ocean forecast data not available');
        }

        const data = await response.json();
        displayOceanForecast(data);
    } catch (error) {
        console.error('Failed to load ocean forecast:', error);
        document.getElementById('oceanForecastContainer').innerHTML =
            '<p style="color: red;">統合海洋予報データの取得に失敗しました</p>';
    }
}

function displayOceanForecast(data) {
    const container = document.getElementById('oceanForecastContainer');

    if (!data || !data.forecasts || data.forecasts.length === 0) {
        container.innerHTML = '<p>予報データがありません</p>';
        return;
    }

    // 週間サマリー
    const summary = data.summary;
    const workableRate = summary.workable_rate_pct;

    let summaryHTML = `
        <div class="ocean-forecast-summary" style="background: #f0f8ff; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="margin-top: 0;">📊 週間作業可能率</h3>
            <div style="font-size: 32px; font-weight: bold; color: ${workableRate >= 70 ? '#28a745' : workableRate >= 50 ? '#ffc107' : '#dc3545'};">
                ${workableRate}%
            </div>
            <p style="margin: 10px 0 5px 0;">作業可能日: ${summary.workable_days}/${summary.total_days}日</p>
            <div style="display: flex; gap: 15px; margin-top: 10px;">
                <div><span style="color: #28a745;">●</span> 理想的: ${summary.excellent_days}日</div>
                <div><span style="color: #ffc107;">●</span> ギリギリ: ${summary.acceptable_days}日</div>
                <div><span style="color: #dc3545;">●</span> 不適: ${summary.unsuitable_days}日</div>
            </div>
        </div>
    `;

    // 日別予報
    let forecastHTML = '<div class="ocean-forecast-daily">';

    data.forecasts.forEach(day => {
        const colorMap = {
            'green': '#28a745',
            'yellow': '#ffc107',
            'orange': '#fd7e14',
            'red': '#dc3545'
        };

        const bgColor = colorMap[day.color] || '#6c757d';
        const textColor = day.color === 'yellow' ? '#000' : '#fff';

        forecastHTML += `
            <div class="forecast-day-card" style="
                border: 2px solid ${bgColor};
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 15px;
                background: ${day.color === 'green' ? '#e8f5e9' :
                             day.color === 'yellow' ? '#fff3cd' :
                             day.color === 'orange' ? '#ffe5cc' : '#f8d7da'};
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h4 style="margin: 0;">${day.date} (${getDayOfWeek(day.date)})</h4>
                    <span style="
                        background: ${bgColor};
                        color: ${textColor};
                        padding: 5px 15px;
                        border-radius: 20px;
                        font-weight: bold;
                    ">${day.viability}</span>
                </div>

                <div style="margin: 10px 0;">
                    <strong>作業可能時間:</strong> ${day.work_window}
                    <span style="font-size: 24px; font-weight: bold; margin-left: 10px;">
                        ${day.continuous_hours}時間
                    </span>
                </div>

                <div style="background: white; padding: 10px; border-radius: 5px; margin: 10px 0;">
                    <div style="margin-bottom: 5px;">
                        <strong>霧消散:</strong> ${day.fog_clear_time}
                        ${day.fog_type === 'MORNING_FOG' ? '🌫️ (朝霧)' :
                          day.fog_type === 'ALL_DAY_FOG' ? '🌫️🌫️ (終日霧)' : '☀️'}
                    </div>
                    <div>
                        <strong>降水リスク:</strong>
                        <span style="color: ${
                            day.precipitation_risk === 'CRITICAL' || day.precipitation_risk === 'HIGH' ? 'red' :
                            day.precipitation_risk === 'MODERATE' ? 'orange' : 'green'
                        };">
                            ${day.precipitation_risk}
                        </span>
                    </div>
                </div>

                <div style="
                    background: ${bgColor};
                    color: ${textColor};
                    padding: 10px;
                    border-radius: 5px;
                    font-weight: bold;
                ">
                    ${day.action}
                </div>

                <div style="margin-top: 10px; font-size: 14px; color: #666;">
                    ${day.recommendation}
                </div>
            </div>
        `;
    });

    forecastHTML += '</div>';

    container.innerHTML = summaryHTML + forecastHTML;
}

function getDayOfWeek(dateStr) {
    const days = ['日', '月', '火', '水', '木', '金', '土'];
    const date = new Date(dateStr);
    return days[date.getDay()];
}

// ページ読み込み時に統合海洋予報を取得
document.addEventListener('DOMContentLoaded', function() {
    // 既存の初期化処理の後に追加
    loadOceanIntegratedForecast();

    // 5分ごとに更新
    setInterval(loadOceanIntegratedForecast, 5 * 60 * 1000);
});
