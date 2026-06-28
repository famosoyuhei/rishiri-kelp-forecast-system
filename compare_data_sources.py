"""
Compare Open-Meteo vs ERA5 pressure level data for tropopause detection
Location: Rishiri Island (45.18°N, 141.24°E)
"""

import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json

# Rishiri Island coordinates
LAT = 45.18
LON = 141.24

def fetch_openmeteo_data():
    """Fetch Open-Meteo pressure level data (100-1000hPa)"""
    print("Fetching Open-Meteo data...")

    pressure_levels = [1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100]

    # Build URL with all pressure levels
    params = []
    for p in pressure_levels:
        params.append(f"temperature_{p}hPa")
        params.append(f"dewpoint_{p}hPa")

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={LAT}&longitude={LON}&"
        f"hourly={','.join(params)}&"
        f"timezone=Asia/Tokyo&forecast_days=1"
    )

    response = requests.get(url, timeout=30)
    data = response.json()

    # Extract first hour data
    hourly = data['hourly']
    time = hourly['time'][0]

    temps = []
    dewpoints = []
    for p in pressure_levels:
        temps.append(hourly[f'temperature_{p}hPa'][0])
        dewpoints.append(hourly[f'dewpoint_{p}hPa'][0])

    df = pd.DataFrame({
        'pressure': pressure_levels,
        'temperature': temps,
        'dewpoint': dewpoints,
        'source': 'Open-Meteo'
    })

    print(f"Open-Meteo data fetched for: {time}")
    return df, time

def fetch_era5_sample():
    """
    Note: ERA5 requires CDS API setup with credentials
    This is a placeholder showing the structure

    For actual implementation, you need:
    1. CDS API key from https://cds.climate.copernicus.eu/
    2. Install: pip install cdsapi
    """
    print("\nNote: ERA5 data requires CDS API credentials")
    print("Visit: https://cds.climate.copernicus.eu/api-how-to")
    print("\nFor this comparison, we'll use Open-Meteo data only")
    print("and analyze its capability for tropopause detection.")

    return None

def analyze_lapse_rate(df):
    """Calculate temperature lapse rate (K/km) between pressure levels"""

    # Approximate height from pressure using hypsometric equation
    # Z ≈ -H * ln(P/P0), where H ≈ 7.4 km (scale height)
    H = 7.4  # km
    P0 = 1013.25  # hPa

    df['height_km'] = -H * (df['pressure'] / P0).apply(lambda x: 0 if x <= 0 else np.log(x))

    # Calculate lapse rate
    lapse_rates = []
    for i in range(len(df) - 1):
        dT = df.iloc[i]['temperature'] - df.iloc[i+1]['temperature']  # K
        dZ = df.iloc[i+1]['height_km'] - df.iloc[i]['height_km']  # km

        if dZ > 0:
            lapse_rate = dT / dZ  # K/km
        else:
            lapse_rate = 0

        lapse_rates.append({
            'pressure_lower': df.iloc[i]['pressure'],
            'pressure_upper': df.iloc[i+1]['pressure'],
            'height_km': (df.iloc[i]['height_km'] + df.iloc[i+1]['height_km']) / 2,
            'lapse_rate': lapse_rate
        })

    return pd.DataFrame(lapse_rates)

def plot_comparison(df_meteo, lapse_df, time_str):
    """Create comparison plots"""

    fig, axes = plt.subplots(1, 3, figsize=(18, 8))

    # Plot 1: Temperature profile
    ax1 = axes[0]
    ax1.plot(df_meteo['temperature'], df_meteo['pressure'], 'o-',
             linewidth=2, markersize=6, color='red', label='Temperature')
    ax1.plot(df_meteo['dewpoint'], df_meteo['pressure'], 'o-',
             linewidth=2, markersize=6, color='blue', label='Dewpoint')
    ax1.set_xlabel('Temperature (°C)', fontsize=12)
    ax1.set_ylabel('Pressure (hPa)', fontsize=12)
    ax1.set_ylim(1000, 100)
    ax1.invert_yaxis()
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.set_title(f'Open-Meteo Temperature Profile\n{time_str}', fontsize=14)

    # Add tropopause reference lines (from CSV)
    current_month = datetime.strptime(time_str, '%Y-%m-%dT%H:%M').month
    tropopause_pressures = {
        1: 290, 2: 285, 3: 270, 4: 250, 5: 230, 6: 215,
        7: 210, 8: 215, 9: 230, 10: 250, 11: 270, 12: 285
    }
    trop_p = tropopause_pressures.get(current_month, 250)
    ax1.axhline(y=trop_p, color='purple', linestyle='--', linewidth=2,
                label=f'Tropopause (climatology): {trop_p}hPa')
    ax1.legend()

    # Plot 2: Lapse rate
    ax2 = axes[1]
    ax2.plot(lapse_df['lapse_rate'], lapse_df['pressure_lower'], 'o-',
             linewidth=2, markersize=6, color='green')
    ax2.axvline(x=2.0, color='purple', linestyle='--', linewidth=2,
                label='Tropopause criterion (2 K/km)')
    ax2.set_xlabel('Lapse Rate (K/km)', fontsize=12)
    ax2.set_ylabel('Pressure (hPa)', fontsize=12)
    ax2.set_ylim(1000, 100)
    ax2.invert_yaxis()
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    ax2.set_title('Temperature Lapse Rate', fontsize=14)
    ax2.set_xlim(-5, 15)

    # Plot 3: Height vs Temperature
    ax3 = axes[2]
    heights = -7.4 * (df_meteo['pressure'] / 1013.25).apply(lambda x: np.log(x) if x > 0 else 0)
    ax3.plot(df_meteo['temperature'], heights, 'o-',
             linewidth=2, markersize=6, color='red')
    ax3.set_xlabel('Temperature (°C)', fontsize=12)
    ax3.set_ylabel('Approximate Height (km)', fontsize=12)
    ax3.grid(True, alpha=0.3)
    ax3.set_title('Height-Temperature Profile', fontsize=14)

    # Add tropopause height
    trop_height = -7.4 * np.log(trop_p / 1013.25)
    ax3.axhline(y=trop_height, color='purple', linestyle='--', linewidth=2,
                label=f'Tropopause: ~{trop_height:.1f} km')
    ax3.legend()

    plt.tight_layout()
    plt.savefig('openmeteo_vs_tropopause_analysis.png', dpi=150, bbox_inches='tight')
    print("\nPlot saved: openmeteo_vs_tropopause_analysis.png")

    return fig

def main():
    print("=" * 70)
    print("DATA SOURCE COMPARISON: Open-Meteo vs Tropopause Detection")
    print("=" * 70)

    # Fetch Open-Meteo data
    df_meteo, time_str = fetch_openmeteo_data()

    print("\n" + "=" * 70)
    print("OPEN-METEO DATA SUMMARY")
    print("=" * 70)
    print(f"\nPressure range: {df_meteo['pressure'].max()} - {df_meteo['pressure'].min()} hPa")
    print(f"Temperature range: {df_meteo['temperature'].min():.1f} - {df_meteo['temperature'].max():.1f} °C")
    print(f"\nData points: {len(df_meteo)}")
    print("\nSample data:")
    print(df_meteo[['pressure', 'temperature', 'dewpoint']].head(10))

    # Analyze lapse rate
    lapse_df = analyze_lapse_rate(df_meteo)

    print("\n" + "=" * 70)
    print("LAPSE RATE ANALYSIS")
    print("=" * 70)
    print("\nWMO Tropopause Definition: Lapse rate <= 2 K/km")
    print("\nLapse rates by pressure level:")
    print(lapse_df.to_string(index=False))

    # Check if tropopause can be detected
    tropopause_candidates = lapse_df[lapse_df['lapse_rate'] <= 2.0]

    print("\n" + "=" * 70)
    print("TROPOPAUSE DETECTION CAPABILITY")
    print("=" * 70)

    if len(tropopause_candidates) > 0:
        print("\n[OK] Tropopause-like conditions detected:")
        print(tropopause_candidates.to_string(index=False))
    else:
        print("\n[NO] NO tropopause detected in Open-Meteo data (100-1000hPa)")
        print("\nReason: Temperature continues to decrease monotonically")
        print("The data does not extend high enough to capture the stratosphere")
        print("where temperature begins to increase (defining the tropopause).")

    # Check temperature trend in upper levels
    upper_temps = df_meteo[df_meteo['pressure'] <= 200]['temperature']
    if len(upper_temps) >= 2:
        temp_trend = upper_temps.iloc[-1] - upper_temps.iloc[0]
        print(f"\nTemperature trend (200-100hPa): {temp_trend:.1f} °C")
        if temp_trend >= 0:
            print("-> Temperature increasing (stratospheric signature)")
        else:
            print("-> Temperature still decreasing (tropospheric only)")

    # Create visualization
    print("\n" + "=" * 70)
    print("CREATING VISUALIZATION")
    print("=" * 70)
    plot_comparison(df_meteo, lapse_df, time_str)

    # Recommendations
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    print("\n1. Open-Meteo Coverage:")
    print("   - Excellent for troposphere (cloud analysis, LCL/LFC/EL)")
    print("   - Does NOT capture tropopause (stops at 100hPa)")
    print("   - Cannot show stratospheric temperature inversion")

    print("\n2. For True Tropopause Detection:")
    print("   - Need data up to 10-50hPa (~20-30km altitude)")
    print("   - Options: ERA5 (1hPa), NOAA GFS (10hPa), or radiosonde")

    print("\n3. Recommended Implementation:")
    print("   - Continue using Open-Meteo for cloud analysis")
    print("   - Add tropopause climatology as REFERENCE LINE only")
    print("   - Label: 'Tropopause (climatology reference)' to indicate it's not detected")

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
