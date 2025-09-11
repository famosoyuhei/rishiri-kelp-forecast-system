#!/usr/bin/env python3
"""
大気安定度指標計算システム
Atmospheric Stability Analyzer System

利尻島局地気象予測のため、鉛直p速度・SSI・相当温位等の
大気安定度指標を計算し、対流・降水予測に活用する。
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Union
from datetime import datetime
import math
import logging
from scipy.integrate import trapezoid
from scipy.interpolate import interp1d

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AtmosphericProfile:
    """大気プロファイルデータ"""
    timestamp: datetime
    latitude: float
    longitude: float
    pressure_levels: np.ndarray  # hPa
    temperature: np.ndarray      # °C
    dewpoint: np.ndarray         # °C
    wind_speed: np.ndarray       # m/s
    wind_direction: np.ndarray   # degrees
    geopotential_height: np.ndarray  # m

@dataclass
class StabilityIndices:
    """大気安定度指標"""
    timestamp: datetime
    location: Tuple[float, float]  # (lat, lon)
    ssi: float                     # Showalter Stability Index
    cape: float                    # Convective Available Potential Energy (J/kg)
    cin: float                     # Convective Inhibition (J/kg)
    lifted_index: float            # Lifted Index
    k_index: float                 # K Index
    total_totals: float            # Total Totals Index
    vertical_p_velocity: float     # Pa/s (omega)
    equivalent_potential_temp_850: float  # K
    precipitable_water: float      # kg/m²

class AtmosphericStabilityAnalyzer:
    """大気安定度解析クラス"""
    
    def __init__(self):
        # 標準気圧レベル
        self.standard_levels = np.array([
            1000, 925, 850, 700, 500, 400, 300, 250, 200, 150, 100
        ])
        
        # 物理定数
        self.R_d = 287.0      # 乾燥空気の気体定数 (J/kg/K)
        self.R_v = 461.5      # 水蒸気の気体定数 (J/kg/K)
        self.c_p = 1004.0     # 定圧比熱 (J/kg/K)
        self.L_v = 2.5e6      # 水の潜熱 (J/kg)
        self.g = 9.81         # 重力加速度 (m/s²)
        self.epsilon = 0.622  # 分子量比 (Mv/Md)
        
    def calculate_stability_indices(self, profile: AtmosphericProfile) -> StabilityIndices:
        """大気安定度指標計算"""
        
        # 各指標を計算
        ssi = self._calculate_ssi(profile)
        cape, cin = self._calculate_cape_cin(profile)
        lifted_index = self._calculate_lifted_index(profile)
        k_index = self._calculate_k_index(profile)
        total_totals = self._calculate_total_totals(profile)
        vertical_p_velocity = self._calculate_vertical_p_velocity(profile)
        theta_e_850 = self._calculate_equivalent_potential_temperature_850(profile)
        precipitable_water = self._calculate_precipitable_water(profile)
        
        indices = StabilityIndices(
            timestamp=profile.timestamp,
            location=(profile.latitude, profile.longitude),
            ssi=ssi,
            cape=cape,
            cin=cin,
            lifted_index=lifted_index,
            k_index=k_index,
            total_totals=total_totals,
            vertical_p_velocity=vertical_p_velocity,
            equivalent_potential_temp_850=theta_e_850,
            precipitable_water=precipitable_water
        )
        
        logger.info(f"Stability indices calculated for {profile.timestamp}")
        return indices
    
    def _calculate_ssi(self, profile: AtmosphericProfile) -> float:
        """ショワルター安定指数計算"""
        try:
            # 850hPaと500hPaの値を取得
            temp_850 = self._interpolate_to_level(profile.pressure_levels, 
                                                profile.temperature, 850)
            temp_500 = self._interpolate_to_level(profile.pressure_levels, 
                                                profile.temperature, 500)
            dewpoint_850 = self._interpolate_to_level(profile.pressure_levels, 
                                                    profile.dewpoint, 850)
            
            if any(x is None for x in [temp_850, temp_500, dewpoint_850]):
                return np.nan
            
            # 850hPaの空気塊を500hPaまで乾燥断熱上昇させた場合の温度
            theta_850 = temp_850 + 273.15  # K
            theta_500_dry = theta_850 * (500/850)**(self.R_d/self.c_p)
            temp_500_lifted = theta_500_dry - 273.15  # °C
            
            # SSI = T_500_env - T_500_lifted
            ssi = temp_500 - temp_500_lifted
            
            return ssi
        
        except Exception as e:
            logger.error(f"Error calculating SSI: {e}")
            return np.nan
    
    def _calculate_cape_cin(self, profile: AtmosphericProfile) -> Tuple[float, float]:
        """CAPE/CIN計算"""
        try:
            # 地表からのパーセル上昇を計算
            surface_pressure = np.max(profile.pressure_levels)
            surface_temp = profile.temperature[0] + 273.15  # K
            surface_dewpoint = profile.dewpoint[0] + 273.15  # K
            
            # 混合比計算
            surface_mixing_ratio = self._calculate_mixing_ratio(surface_dewpoint, surface_pressure)
            
            cape = 0.0
            cin = 0.0
            
            # 各レベルでパーセルと環境の温度を比較
            for i in range(len(profile.pressure_levels) - 1):
                p_level = profile.pressure_levels[i]
                if p_level >= surface_pressure:
                    continue
                
                # パーセル温度（断熱上昇）
                parcel_temp = self._calculate_parcel_temperature(
                    surface_temp, surface_pressure, surface_mixing_ratio, p_level
                )
                
                # 環境温度
                env_temp = profile.temperature[i] + 273.15
                
                # 高度差
                if i > 0:
                    dz = (profile.geopotential_height[i] - profile.geopotential_height[i-1])
                    
                    # パーセルが環境より暖かい場合はCAPE、冷たい場合はCIN
                    if parcel_temp > env_temp:
                        cape += self.g * (parcel_temp - env_temp) / env_temp * dz
                    else:
                        cin += self.g * (env_temp - parcel_temp) / env_temp * dz
            
            return cape, cin
        
        except Exception as e:
            logger.error(f"Error calculating CAPE/CIN: {e}")
            return np.nan, np.nan
    
    def _calculate_lifted_index(self, profile: AtmosphericProfile) -> float:
        """リフテッド指数計算"""
        try:
            # 500hPaの環境温度
            temp_500_env = self._interpolate_to_level(profile.pressure_levels, 
                                                    profile.temperature, 500)
            
            # 地表の空気塊を500hPaまで上昇させた温度
            surface_temp = profile.temperature[0] + 273.15
            surface_pressure = np.max(profile.pressure_levels)
            
            # 乾燥断熱上昇
            theta = surface_temp * (1000/surface_pressure)**(self.R_d/self.c_p)
            temp_500_lifted = theta * (500/1000)**(self.R_d/self.c_p) - 273.15
            
            return temp_500_env - temp_500_lifted
        
        except Exception as e:
            logger.error(f"Error calculating Lifted Index: {e}")
            return np.nan
    
    def _calculate_k_index(self, profile: AtmosphericProfile) -> float:
        """K指数計算"""
        try:
            temp_850 = self._interpolate_to_level(profile.pressure_levels, profile.temperature, 850)
            temp_700 = self._interpolate_to_level(profile.pressure_levels, profile.temperature, 700)
            temp_500 = self._interpolate_to_level(profile.pressure_levels, profile.temperature, 500)
            dewpoint_850 = self._interpolate_to_level(profile.pressure_levels, profile.dewpoint, 850)
            dewpoint_700 = self._interpolate_to_level(profile.pressure_levels, profile.dewpoint, 700)
            
            if any(x is None for x in [temp_850, temp_700, temp_500, dewpoint_850, dewpoint_700]):
                return np.nan
            
            k_index = (temp_850 - temp_500) + dewpoint_850 - (temp_700 - dewpoint_700)
            return k_index
        
        except Exception as e:
            logger.error(f"Error calculating K Index: {e}")
            return np.nan
    
    def _calculate_total_totals(self, profile: AtmosphericProfile) -> float:
        """トータル・トータルズ指数計算"""
        try:
            temp_850 = self._interpolate_to_level(profile.pressure_levels, profile.temperature, 850)
            temp_500 = self._interpolate_to_level(profile.pressure_levels, profile.temperature, 500)
            dewpoint_850 = self._interpolate_to_level(profile.pressure_levels, profile.dewpoint, 850)
            
            if any(x is None for x in [temp_850, temp_500, dewpoint_850]):
                return np.nan
            
            # VT (Vertical Totals) + CT (Cross Totals)
            vt = temp_850 - temp_500
            ct = dewpoint_850 - temp_500
            total_totals = vt + ct
            
            return total_totals
        
        except Exception as e:
            logger.error(f"Error calculating Total Totals: {e}")
            return np.nan
    
    def _calculate_vertical_p_velocity(self, profile: AtmosphericProfile) -> float:
        """鉛直p速度計算（オメガ）"""
        try:
            # 簡易計算：風速の鉛直シアーから推定
            if len(profile.wind_speed) < 3:
                return np.nan
            
            # 風速の鉛直勾配
            dp = np.diff(profile.pressure_levels)
            du = np.diff(profile.wind_speed)
            
            # 平均的な鉛直シアー
            mean_shear = np.mean(du / dp) if len(du) > 0 else 0
            
            # オメガの簡易推定（実際にはより複雑な計算が必要）
            omega = -mean_shear * 100  # Pa/s (仮の係数)
            
            return omega
        
        except Exception as e:
            logger.error(f"Error calculating vertical p-velocity: {e}")
            return np.nan
    
    def _calculate_equivalent_potential_temperature_850(self, profile: AtmosphericProfile) -> float:
        """850hPa相当温位計算"""
        try:
            temp_850 = self._interpolate_to_level(profile.pressure_levels, profile.temperature, 850)
            dewpoint_850 = self._interpolate_to_level(profile.pressure_levels, profile.dewpoint, 850)
            
            if temp_850 is None or dewpoint_850 is None:
                return np.nan
            
            # 相当温位計算
            temp_k = temp_850 + 273.15
            dewpoint_k = dewpoint_850 + 273.15
            
            # 混合比
            mixing_ratio = self._calculate_mixing_ratio(dewpoint_k, 850)
            
            # 温位
            theta = temp_k * (1000/850)**(self.R_d/self.c_p)
            
            # 相当温位
            theta_e = theta * np.exp((self.L_v * mixing_ratio) / (self.c_p * temp_k))
            
            return theta_e
        
        except Exception as e:
            logger.error(f"Error calculating equivalent potential temperature: {e}")
            return np.nan
    
    def _calculate_precipitable_water(self, profile: AtmosphericProfile) -> float:
        """可降水量計算"""
        try:
            precipitable_water = 0.0
            
            for i in range(len(profile.pressure_levels) - 1):
                p1 = profile.pressure_levels[i] * 100      # Pa
                p2 = profile.pressure_levels[i+1] * 100    # Pa
                
                # 各レベルの混合比
                dewpoint1 = profile.dewpoint[i] + 273.15
                dewpoint2 = profile.dewpoint[i+1] + 273.15
                
                mixing_ratio1 = self._calculate_mixing_ratio(dewpoint1, profile.pressure_levels[i])
                mixing_ratio2 = self._calculate_mixing_ratio(dewpoint2, profile.pressure_levels[i+1])
                
                # 平均混合比
                mean_mixing_ratio = (mixing_ratio1 + mixing_ratio2) / 2
                
                # 層の可降水量
                dp = p1 - p2  # Pa
                layer_pw = mean_mixing_ratio * dp / self.g  # kg/m²
                
                precipitable_water += layer_pw
            
            return precipitable_water
        
        except Exception as e:
            logger.error(f"Error calculating precipitable water: {e}")
            return np.nan
    
    def _calculate_mixing_ratio(self, dewpoint_k: float, pressure_hpa: float) -> float:
        """混合比計算"""
        try:
            # 飽和水蒸気圧（Magnus式）
            es = 6.112 * np.exp(17.67 * (dewpoint_k - 273.15) / (dewpoint_k - 29.65))  # hPa
            
            # 混合比
            mixing_ratio = self.epsilon * es / (pressure_hpa - es)  # kg/kg
            
            return mixing_ratio
        
        except Exception as e:
            logger.error(f"Error calculating mixing ratio: {e}")
            return 0.0
    
    def _calculate_parcel_temperature(self, surface_temp: float, surface_pressure: float,
                                    mixing_ratio: float, target_pressure: float) -> float:
        """パーセル温度計算（断熱上昇）"""
        try:
            # 乾燥断熱上昇
            theta = surface_temp * (1000/surface_pressure)**(self.R_d/self.c_p)
            parcel_temp = theta * (target_pressure/1000)**(self.R_d/self.c_p)
            
            return parcel_temp
        
        except Exception as e:
            logger.error(f"Error calculating parcel temperature: {e}")
            return np.nan
    
    def _interpolate_to_level(self, pressure_levels: np.ndarray, values: np.ndarray, 
                            target_pressure: float) -> Optional[float]:
        """指定気圧レベルへの補間"""
        try:
            if target_pressure in pressure_levels:
                idx = np.where(pressure_levels == target_pressure)[0][0]
                return values[idx]
            
            # 線形補間
            if (target_pressure < np.min(pressure_levels) or 
                target_pressure > np.max(pressure_levels)):
                return None
            
            # 気圧の降順にソート
            sorted_indices = np.argsort(pressure_levels)[::-1]
            sorted_pressures = pressure_levels[sorted_indices]
            sorted_values = values[sorted_indices]
            
            interpolated = np.interp(target_pressure, sorted_pressures, sorted_values)
            return interpolated
        
        except Exception as e:
            logger.error(f"Error in interpolation: {e}")
            return None
    
    def interpret_stability_indices(self, indices: StabilityIndices) -> Dict[str, str]:
        """安定度指標の解釈"""
        interpretation = {
            'timestamp': indices.timestamp.isoformat(),
            'location': f"({indices.location[0]:.3f}, {indices.location[1]:.3f})"
        }
        
        # SSI解釈
        if not np.isnan(indices.ssi):
            if indices.ssi < -3:
                interpretation['ssi'] = f"SSI={indices.ssi:.1f}: 非常に不安定（雷雨発生の可能性大）"
            elif indices.ssi < -1:
                interpretation['ssi'] = f"SSI={indices.ssi:.1f}: 不安定（雷雨発生の可能性）"
            elif indices.ssi < 1:
                interpretation['ssi'] = f"SSI={indices.ssi:.1f}: やや不安定"
            else:
                interpretation['ssi'] = f"SSI={indices.ssi:.1f}: 安定"
        else:
            interpretation['ssi'] = "SSI: データ不足"
        
        # CAPE解釈
        if not np.isnan(indices.cape):
            if indices.cape > 2500:
                interpretation['cape'] = f"CAPE={indices.cape:.0f}J/kg: 強い対流（激しい雷雨の可能性）"
            elif indices.cape > 1000:
                interpretation['cape'] = f"CAPE={indices.cape:.0f}J/kg: 中程度の対流（雷雨の可能性）"
            elif indices.cape > 100:
                interpretation['cape'] = f"CAPE={indices.cape:.0f}J/kg: 弱い対流"
            else:
                interpretation['cape'] = f"CAPE={indices.cape:.0f}J/kg: 対流抑制"
        else:
            interpretation['cape'] = "CAPE: データ不足"
        
        # K指数解釈
        if not np.isnan(indices.k_index):
            if indices.k_index > 40:
                interpretation['k_index'] = f"K指数={indices.k_index:.1f}: 雷雨発生の可能性大"
            elif indices.k_index > 25:
                interpretation['k_index'] = f"K指数={indices.k_index:.1f}: 雷雨発生の可能性"
            else:
                interpretation['k_index'] = f"K指数={indices.k_index:.1f}: 雷雨発生の可能性小"
        else:
            interpretation['k_index'] = "K指数: データ不足"
        
        # 鉛直p速度解釈
        if not np.isnan(indices.vertical_p_velocity):
            if indices.vertical_p_velocity < -0.1:
                interpretation['omega'] = f"ω={indices.vertical_p_velocity:.2f}Pa/s: 上昇流（降水有利）"
            elif indices.vertical_p_velocity > 0.1:
                interpretation['omega'] = f"ω={indices.vertical_p_velocity:.2f}Pa/s: 下降流（晴天有利）"
            else:
                interpretation['omega'] = f"ω={indices.vertical_p_velocity:.2f}Pa/s: 中性"
        else:
            interpretation['omega'] = "鉛直p速度: データ不足"
        
        return interpretation
    
    def create_stability_diagram(self, indices: StabilityIndices, 
                               output_file: str = None) -> str:
        """安定度指標図作成"""
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle(f'Atmospheric Stability Analysis - {indices.timestamp.strftime("%Y-%m-%d %H:%M")}')
        
        # SSI
        ax1 = axes[0, 0]
        ssi_levels = [-10, -5, -3, -1, 0, 1, 3, 5, 10]
        ssi_colors = ['darkred', 'red', 'orange', 'yellow', 'lightgreen', 'green', 'blue', 'darkblue']
        ssi_color_idx = np.digitize(indices.ssi, ssi_levels) - 1
        ssi_color_idx = max(0, min(len(ssi_colors)-1, ssi_color_idx))
        
        ax1.bar(['SSI'], [indices.ssi], color=ssi_colors[ssi_color_idx])
        ax1.set_ylabel('SSI')
        ax1.set_title('Showalter Stability Index')
        ax1.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax1.set_ylim(-10, 5)
        
        # CAPE/CIN
        ax2 = axes[0, 1]
        cape_cin = [indices.cape, -indices.cin] if not np.isnan(indices.cin) else [indices.cape, 0]
        colors = ['red' if cape_cin[0] > 0 else 'blue', 'blue' if cape_cin[1] < 0 else 'red']
        ax2.bar(['CAPE', 'CIN'], cape_cin, color=colors)
        ax2.set_ylabel('Energy (J/kg)')
        ax2.set_title('CAPE & CIN')
        ax2.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        
        # K指数
        ax3 = axes[1, 0]
        k_levels = [0, 15, 25, 35, 45]
        k_colors = ['blue', 'lightblue', 'yellow', 'orange', 'red']
        k_color_idx = np.digitize(indices.k_index, k_levels) - 1
        k_color_idx = max(0, min(len(k_colors)-1, k_color_idx))
        
        ax3.bar(['K Index'], [indices.k_index], color=k_colors[k_color_idx])
        ax3.set_ylabel('K Index')
        ax3.set_title('K Index')
        ax3.axhline(y=25, color='red', linestyle='--', alpha=0.5, label='Thunderstorm threshold')
        ax3.legend()
        
        # 相当温位・可降水量
        ax4 = axes[1, 1]
        theta_e_normalized = (indices.equivalent_potential_temp_850 - 300) / 50  # 正規化
        pw_normalized = indices.precipitable_water / 30  # 正規化
        
        ax4.bar(['θe (850hPa)', 'PW'], [theta_e_normalized, pw_normalized], 
               color=['purple', 'cyan'])
        ax4.set_ylabel('Normalized values')
        ax4.set_title('Equivalent Potential Temp & Precipitable Water')
        
        plt.tight_layout()
        
        if output_file is None:
            timestamp_str = indices.timestamp.strftime("%Y%m%d_%H%M")
            output_file = f"stability_analysis_{timestamp_str}.png"
        
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.show()
        
        logger.info(f"Stability diagram saved: {output_file}")
        return output_file

def create_synthetic_atmospheric_profile() -> AtmosphericProfile:
    """合成大気プロファイル作成（テスト用）"""
    # 標準大気を基準とした利尻島上空のプロファイル
    pressure_levels = np.array([1000, 925, 850, 700, 500, 400, 300, 250, 200])
    
    # 気温（標準大気 + ランダム変動）
    standard_temps = np.array([15, 11, 7, -3, -17, -27, -41, -48, -56])  # °C
    temperature = standard_temps + np.random.normal(0, 2, len(pressure_levels))
    
    # 露点（気温より低く設定）
    dewpoint = temperature - np.random.uniform(5, 20, len(pressure_levels))
    
    # 風速・風向
    wind_speed = 5 + np.random.normal(0, 5, len(pressure_levels))
    wind_speed = np.maximum(wind_speed, 0)  # 負の値を除去
    wind_direction = np.random.uniform(0, 360, len(pressure_levels))
    
    # ジオポテンシャル高度（標準大気近似）
    geopotential_height = np.array([0, 762, 1457, 3012, 5574, 7185, 9164, 10363, 11784])
    
    profile = AtmosphericProfile(
        timestamp=datetime.now(),
        latitude=45.1821,  # 利尻山
        longitude=141.2421,
        pressure_levels=pressure_levels,
        temperature=temperature,
        dewpoint=dewpoint,
        wind_speed=wind_speed,
        wind_direction=wind_direction,
        geopotential_height=geopotential_height
    )
    
    return profile

def main():
    """メイン実行関数（テスト用）"""
    print("=== Atmospheric Stability Analyzer Test ===")
    
    # 安定度解析器初期化
    analyzer = AtmosphericStabilityAnalyzer()
    
    # テスト用大気プロファイル作成
    profile = create_synthetic_atmospheric_profile()
    print(f"Created atmospheric profile with {len(profile.pressure_levels)} levels")
    
    # 安定度指標計算
    indices = analyzer.calculate_stability_indices(profile)
    
    # 結果表示
    print(f"\nStability Indices for {indices.timestamp}:")
    print(f"  SSI: {indices.ssi:.2f}")
    print(f"  CAPE: {indices.cape:.0f} J/kg")
    print(f"  CIN: {indices.cin:.0f} J/kg")
    print(f"  Lifted Index: {indices.lifted_index:.2f}")
    print(f"  K Index: {indices.k_index:.1f}")
    print(f"  Total Totals: {indices.total_totals:.1f}")
    print(f"  Vertical p-velocity: {indices.vertical_p_velocity:.3f} Pa/s")
    print(f"  θe (850hPa): {indices.equivalent_potential_temp_850:.1f} K")
    print(f"  Precipitable Water: {indices.precipitable_water:.1f} kg/m²")
    
    # 解釈
    interpretation = analyzer.interpret_stability_indices(indices)
    print(f"\nInterpretation:")
    for key, value in interpretation.items():
        if key not in ['timestamp', 'location']:
            print(f"  {value}")
    
    # 安定度図作成
    diagram_file = analyzer.create_stability_diagram(indices, "test_stability_analysis.png")
    
    print(f"\nStability analysis completed!")
    print(f"Diagram saved: {diagram_file}")

if __name__ == "__main__":
    main()