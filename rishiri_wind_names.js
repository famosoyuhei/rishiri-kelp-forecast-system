/**
 * 利尻島伝統風名システム
 * 気象風向を利尻島の伝統的な16方位風名に変換
 *
 * 仕様書に基づく正確な実装
 * 変換式: 干場θ = 177.2° - 気象風向 (負の場合は 537.2° - 気象風向)
 */

// 利尻島16方位伝統風名データベース（仕様書より）
const RISHIRI_WIND_NAMES = [
    { meteoDirection: 0,     kanbaTheta: 177.2, name: "アイ",         reading: "ai",            cardinal: "北" },
    { meteoDirection: 22.5,  kanbaTheta: 154.7, name: "アイシモ",     reading: "aishimo",       cardinal: "北北東" },
    { meteoDirection: 45,    kanbaTheta: 132.2, name: "シモ",         reading: "shimo",         cardinal: "北東" },
    { meteoDirection: 67.5,  kanbaTheta: 109.7, name: "シモヤマセ",   reading: "shimoyamase",   cardinal: "東北東" },
    { meteoDirection: 90,    kanbaTheta: 87.2,  name: "ホンヤマセ",   reading: "honyamase",     cardinal: "東" },
    { meteoDirection: 112.5, kanbaTheta: 64.7,  name: "ヤマセ",       reading: "yamase",        cardinal: "東南東" },
    { meteoDirection: 135,   kanbaTheta: 42.2,  name: "ミナミヤマセ", reading: "minamiyamase",  cardinal: "南東" },
    { meteoDirection: 157.5, kanbaTheta: 19.7,  name: "ミナミヤマ",   reading: "minamiyama",    cardinal: "南南東" },
    { meteoDirection: 180,   kanbaTheta: 357.2, name: "クダリ",       reading: "kudari",        cardinal: "南" },
    { meteoDirection: 202.5, kanbaTheta: 334.7, name: "クダリヒカタ", reading: "kudarihikata",  cardinal: "南南西" },
    { meteoDirection: 225,   kanbaTheta: 312.2, name: "ヒカタ",       reading: "hikata",        cardinal: "南西" },
    { meteoDirection: 247.5, kanbaTheta: 289.7, name: "ニシヒカタ",   reading: "nishihikata",   cardinal: "西南西" },
    { meteoDirection: 270,   kanbaTheta: 267.2, name: "ニシ",         reading: "nishi",         cardinal: "西" },
    { meteoDirection: 292.5, kanbaTheta: 244.7, name: "ニシタマ",     reading: "nishitama",     cardinal: "西北西" },
    { meteoDirection: 315,   kanbaTheta: 222.2, name: "タマ",         reading: "tama",          cardinal: "北西" },
    { meteoDirection: 337.5, kanbaTheta: 199.7, name: "アイタマ",     reading: "aitama",        cardinal: "北北西" }
];

/**
 * 気象風向を利尻島伝統風名に変換
 * @param {number} meteorologicalDirection 気象風向（度、0-360）
 * @returns {string} 利尻島伝統風名
 */
function getRishiriWindName(meteorologicalDirection) {
    if (meteorologicalDirection === null || meteorologicalDirection === undefined) {
        return "--";
    }

    // 0-360度に正規化
    const normalizedDir = ((meteorologicalDirection % 360) + 360) % 360;

    // 最も近い16方位を見つける
    let minDiff = 360;
    let closestWind = RISHIRI_WIND_NAMES[0];

    for (const wind of RISHIRI_WIND_NAMES) {
        let diff = Math.abs(normalizedDir - wind.meteoDirection);
        // 360度境界での最小差を計算
        diff = Math.min(diff, 360 - diff);

        if (diff < minDiff) {
            minDiff = diff;
            closestWind = wind;
        }
    }

    return closestWind.name;
}

/**
 * 気象風向を干場θ座標に変換
 * @param {number} meteorologicalDirection 気象風向（度、0-360）
 * @returns {number} 干場θ座標（度、0-360）
 */
function meteorologicalToKanbaTheta(meteorologicalDirection) {
    if (meteorologicalDirection === null || meteorologicalDirection === undefined) {
        return null;
    }

    let kanbaTheta = 177.2 - meteorologicalDirection;

    // 負の場合は360を加算して正の値にする
    if (kanbaTheta < 0) {
        kanbaTheta += 360;
    }

    return kanbaTheta;
}

/**
 * 伝統風名の詳細情報を取得
 * @param {number} meteorologicalDirection 気象風向（度、0-360）
 * @returns {object} 風名詳細情報
 */
function getRishiriWindDetails(meteorologicalDirection) {
    if (meteorologicalDirection === null || meteorologicalDirection === undefined) {
        return {
            name: "--",
            reading: "--",
            cardinal: "--",
            kanbaTheta: null
        };
    }

    const normalizedDir = ((meteorologicalDirection % 360) + 360) % 360;

    let minDiff = 360;
    let closestWind = RISHIRI_WIND_NAMES[0];

    for (const wind of RISHIRI_WIND_NAMES) {
        let diff = Math.abs(normalizedDir - wind.meteoDirection);
        diff = Math.min(diff, 360 - diff);

        if (diff < minDiff) {
            minDiff = diff;
            closestWind = wind;
        }
    }

    return {
        name: closestWind.name,
        reading: closestWind.reading,
        cardinal: closestWind.cardinal,
        kanbaTheta: meteorologicalToKanbaTheta(meteorologicalDirection)
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

// Node.js環境での exports
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getRishiriWindName,
        meteorologicalToKanbaTheta,
        getRishiriWindDetails,
        RISHIRI_WIND_NAMES
    };
}