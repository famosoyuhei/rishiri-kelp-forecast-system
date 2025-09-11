/**
 * 利尻島特有の16方位風名データベース
 * Rishiri Island Traditional Wind Names Database
 * 
 * Based on research from Peshi Cape wind direction board
 * and traditional Ainu/local knowledge
 */

// 干場極座標θに基づく角度定義（θ=0は南岸境界線、正しい変換式: θ=177.2°-気象風向）
const RISHIRI_WIND_NAMES = {
    // 南系 (θ=0付近、南岸境界線基準) - 南風(180°) -> θ=177.2°-180°=-2.8° -> 357.2°
    357.2: { name: 'クダリ', reading: 'kudari', origin: 'traditional', description: '南' },
    334.7: { name: 'クダリヒカタ', reading: 'kudarihikata', origin: 'traditional', description: '南南西' },
    
    // 西南系 (Southwest) - 南西風(225°) -> θ=177.2°-225°=-47.8° -> 312.2°
    312.2: { name: 'ヒカタ', reading: 'hikata', origin: 'traditional', description: '南西' },
    289.7: { name: 'ニシヒカタ', reading: 'nishihikata', origin: 'traditional', description: '西南西' },
    
    // 西系 (West) - 西風(270°) -> θ=177.2°-270°=-92.8° -> 267.2°
    267.2: { name: 'ニシ', reading: 'nishi', origin: 'traditional', description: '西' },
    244.7: { name: 'ニシタマ', reading: 'nishitama', origin: 'traditional', description: '西北西' },
    
    // 西北系 (Northwest) - 北西風(315°) -> θ=177.2°-315°=-137.8° -> 222.2°
    222.2: { name: 'タマ', reading: 'tama', origin: 'traditional', description: '北西' },
    199.7: { name: 'アイタマ', reading: 'aitama', origin: 'traditional', description: '北北西' },
    
    // 北系 (North) - 北風(0°) -> θ=177.2°-0°=177.2°
    177.2: { name: 'アイ', reading: 'ai', origin: 'traditional', description: '北風' },
    154.7: { name: 'アイシモ・シモ', reading: 'aishimo-shimo', origin: 'traditional', description: '北北東' },
    
    // 東北系 (Northeast) - 北東風(45°) -> θ=177.2°-45°=132.2°
    132.2: { name: 'シモ', reading: 'shimo', origin: 'traditional', description: '北東' },
    109.7: { name: 'シモヤマセ', reading: 'shimoyamase', origin: 'traditional', description: '東北東' },
    
    // 東系 (East) - 東風(90°) -> θ=177.2°-90°=87.2°
    87.2: { name: 'ホンヤマセ', reading: 'honyamase', origin: 'traditional', description: '東' },
    64.7: { name: 'ヤマセ', reading: 'yamase', origin: 'traditional', description: '東南東' },
    
    // 東南系 (Southeast) - 南東風(135°) -> θ=177.2°-135°=42.2°
    42.2: { name: 'ミナミヤマセ', reading: 'minamiyamase', origin: 'traditional', description: '南東' },
    19.7: { name: 'ミナミヤマ', reading: 'minamiyama', origin: 'traditional', description: '南南東' }
};

/**
 * 気象風向角度から利尻島風名を取得（干場極座標θ変換対応）
 * @param {number} meteorologicalDirection - 気象学的風向角度 (0-360度、0°=北)
 * @returns {object} 風名情報
 */
function getRishiriWindName(meteorologicalDirection) {
    // 気象風向を干場極座標θに変換
    // 正しい計算式: θ = 177.2° - 気象風向 または 537.2° - 気象風向
    const HOSHIBA_OFFSET = 177.2;
    let hoshibaTheta = HOSHIBA_OFFSET - meteorologicalDirection;
    
    // 角度を正規化 (0-360度)
    if (hoshibaTheta < 0) {
        hoshibaTheta = 537.2 - meteorologicalDirection;
    }
    hoshibaTheta = ((hoshibaTheta % 360) + 360) % 360;
    
    // 最も近い16方位を見つける
    const angles = Object.keys(RISHIRI_WIND_NAMES).map(Number);
    let closestAngle = angles[0];
    let minDiff = Math.abs(hoshibaTheta - closestAngle);
    
    for (const angle of angles) {
        let diff = Math.abs(hoshibaTheta - angle);
        // 角度の差が180度を超える場合は反対方向で計算
        if (diff > 180) {
            diff = 360 - diff;
        }
        
        if (diff < minDiff) {
            minDiff = diff;
            closestAngle = angle;
        }
    }
    
    return RISHIRI_WIND_NAMES[closestAngle];
}

/**
 * 気象風向を利尻島風名で表示（干場極座標θ対応）
 * @param {number} meteorologicalDirection - 気象学的風向角度
 * @returns {object} 表示用データ
 */
function formatWindDirectionWithRishiriName(meteorologicalDirection) {
    const windName = getRishiriWindName(meteorologicalDirection);
    const arrow = getWindArrow(meteorologicalDirection);
    
    // 干場極座標θに変換した値も含める
    const HOSHIBA_OFFSET = 177.2;
    let hoshibaTheta = HOSHIBA_OFFSET - meteorologicalDirection;
    if (hoshibaTheta < 0) {
        hoshibaTheta = 537.2 - meteorologicalDirection;
    }
    hoshibaTheta = ((hoshibaTheta % 360) + 360) % 360;
    
    return {
        arrow: arrow,
        meteorologicalDirection: Math.round(meteorologicalDirection),
        hoshibaTheta: Math.round(hoshibaTheta * 10) / 10, // 小数点1桁
        rishiriName: windName.name,
        reading: windName.reading,
        description: windName.description,
        displayText: `${windName.name}（${windName.description}）`
    };
}

/**
 * 風向矢印を取得（既存の関数を拡張）
 * @param {number} direction - 風向角度
 * @returns {string} 矢印文字
 */
function getWindArrow(direction) {
    const arrows = ['↓', '↙', '←', '↖', '↑', '↗', '→', '↘'];
    const index = Math.round(direction / 45) % 8;
    return arrows[index];
}

// ES6モジュール用のエクスポート
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        RISHIRI_WIND_NAMES,
        getRishiriWindName,
        formatWindDirectionWithRishiriName,
        getWindArrow
    };
}

// ブラウザ用のグローバル変数として設定
if (typeof window !== 'undefined') {
    window.RishiriWindNames = {
        RISHIRI_WIND_NAMES,
        getRishiriWindName,
        formatWindDirectionWithRishiriName,
        getWindArrow
    };
}