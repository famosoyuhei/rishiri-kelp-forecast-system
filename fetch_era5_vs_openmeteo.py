"""
Compare ERA5 vs Open-Meteo for tropopause detection
ERA5: 1-1000hPa (full stratosphere + troposphere)
Open-Meteo: 100-1000hPa (troposphere only)
"""

import cdsapi
import requests
import xarray as xr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Rishiri Island coordinates
LAT = 45.18
LON = 141.24

def fetch_era5_data():
    """Fetch ERA5 pressure level data from 1 to 1000 hPa"""
    print("=" * 70)
    print("FETCHING ERA5 DATA (1-1000 hPa)")
    print("=" * 70)

    c = cdsapi.Client()

    # Get recent date (ERA5 has ~5 day delay)
    target_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    # All pressure levels from 1 to 1000 hPa
    pressure_levels = [
        1, 2, 3, 5, 7, 10, 20, 30, 50, 70,
        100, 125, 150, 175, 200, 225, 250, 300, 350, 400,
        450, 500, 550, 600, 650, 700, 750, 775, 800, 825,
        850, 875, 900, 925, 950, 975, 1000
    ]

    print(f"\nTarget date: {target_date}")
    print(f"Location: {LAT}°N, {LON}°E")
    print(f"Pressure levels: {len(pressure_levels)} levels (1-1000 hPa)")
    print("\nSubmitting request to CDS API...")

    output_file = 'era5_rishiri_profile.nc'

    try:
        c.retrieve(
            'reanalysis-era5-pressure-levels',
            {
                'product_type': 'reanalysis',
                'variable': ['temperature', 'geopotential'],
                'pressure_level': pressure_levels,
                'year': target_date[:4],
                'month': target_date[5:7],
                'day': target_date[8:10],
                'time': '00:00',
                'area': [LAT + 0.25, LON - 0.25, LAT - 0.25, LON + 0.25],  # Small box around Rishiri
                'format': 'netcdf'
            },
            output_file
        )

        print(f"\n[OK] ERA5 data downloaded: {output_file}")
        return output_file, target_date

    except Exception as e:
        print(f"\n[NO] Error fetching ERA5 data: {e}")
        return None, None

def fetch_openmeteo_data():
    """Fetch Open-Meteo data (100-1000 hPa)"""
    print("\n" + "=" * 70)
    print("FETCHING OPEN-METEO DATA (100-1000 hPa)")
    print("=" * 70)

    pressure_levels = [1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100]

    params = []
    for p in pressure_levels:
        params.append(f"temperature_{p}hPa")

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={LAT}&longitude={LON}&"
        f"hourly={','.join(params)}&"
        f"timezone=Asia/Tokyo&forecast_days=1"
    )

    response = requests.get(url, timeout=30)
    data = response.json()

    hourly = data['hourly']
    time = hourly['time'][0]

    temps = []
    for p in pressure_levels:
        temps.append(hourly[f'temperature_{p}hPa'][0])

    df = pd.DataFrame({
        'pressure': pressure_levels,
        'temperature': temps
    })

    print(f"[OK] Open-Meteo data fetched for: {time}")
    return df, time

def process_era5_data(nc_file):
    """Process ERA5 NetCDF file and extract temperature profile"""
    print("\n" + "=" * 70)
    print("PROCESSING ERA5 DATA")
    print("=" * 70)

    ds = xr.open_dataset(nc_file)

    print(f"  Dimensions: {dict(ds.dims)}")
    print(f"  Variables: {list(ds.data_vars)}")

    # Average over spatial domain and time (single time step)
    temp_da = ds['t'].mean(dim=['latitude', 'longitude', 'valid_time'])
    temp = temp_da.values - 273.15  # K to C
    pressure = ds['pressure_level'].values

    print(f"  Temperature shape: {temp.shape}")
    print(f"  Pressure shape: {pressure.shape}")

    df = pd.DataFrame({
        'pressure': pressure,
        'temperature': temp
    })

    print(f"[OK] ERA5 pressure levels: {len(df)}")
    print(f"  Range: {df['pressure'].min():.0f} - {df['pressure'].max():.0f} hPa")
    print(f"  Temperature range: {df['temperature'].min():.1f} - {df['temperature'].max():.1f} °C")

    return df

def detect_tropopause(df):
    """Detect tropopause using WMO lapse rate criterion"""
    # Calculate lapse rate between levels
    lapse_rates = []

    for i in range(len(df) - 1):
        p1, t1 = df.iloc[i]['pressure'], df.iloc[i]['temperature']
        p2, t2 = df.iloc[i + 1]['pressure'], df.iloc[i + 1]['temperature']

        # Approximate height using hypsometric equation
        H = 7.4  # km
        z1 = -H * np.log(p1 / 1013.25)
        z2 = -H * np.log(p2 / 1013.25)

        dT = t1 - t2  # K
        dZ = z2 - z1  # km

        if dZ > 0:
            lapse_rate = dT / dZ  # K/km
            lapse_rates.append({
                'pressure': (p1 + p2) / 2,
                'height_km': (z1 + z2) / 2,
                'lapse_rate': lapse_rate
            })

    lapse_df = pd.DataFrame(lapse_rates)

    # Find first occurrence of lapse rate <= 2 K/km above 500 hPa
    candidates = lapse_df[(lapse_df['lapse_rate'] <= 2.0) & (lapse_df['pressure'] <= 500)]

    if len(candidates) > 0:
        tropopause = candidates.iloc[0]
        return tropopause['pressure'], tropopause['height_km']

    return None, None

def plot_comparison(df_era5, df_meteo, era5_date, meteo_date):
    """Create comprehensive comparison plot"""
    print("\n" + "=" * 70)
    print("CREATING COMPARISON VISUALIZATION")
    print("=" * 70)

    fig, axes = plt.subplots(1, 2, figsize=(16, 10))

    # Plot 1: Full comparison
    ax1 = axes[0]
    ax1.plot(df_era5['temperature'], df_era5['pressure'], 'o-',
             linewidth=2, markersize=4, color='red', label='ERA5 (1-1000 hPa)', alpha=0.8)
    ax1.plot(df_meteo['temperature'], df_meteo['pressure'], 's-',
             linewidth=2, markersize=6, color='blue', label='Open-Meteo (100-1000 hPa)', alpha=0.8)

    ax1.set_xlabel('Temperature (°C)', fontsize=14)
    ax1.set_ylabel('Pressure (hPa)', fontsize=14)
    ax1.set_ylim(1000, 1)
    ax1.set_yscale('log')
    ax1.invert_yaxis()
    ax1.grid(True, alpha=0.3, which='both')
    ax1.legend(fontsize=12)
    ax1.set_title('ERA5 vs Open-Meteo: Full Vertical Profile\nRishiri Island', fontsize=16, fontweight='bold')

    # Detect tropopause in ERA5
    trop_p_era5, trop_h_era5 = detect_tropopause(df_era5)
    if trop_p_era5:
        ax1.axhline(y=trop_p_era5, color='purple', linestyle='--', linewidth=2.5,
                    label=f'ERA5 Tropopause: {trop_p_era5:.0f} hPa ({trop_h_era5:.1f} km)')
        ax1.legend(fontsize=11)

    # Plot 2: Troposphere zoom (100-1000 hPa)
    ax2 = axes[1]

    # Filter ERA5 to match Open-Meteo range
    df_era5_trop = df_era5[(df_era5['pressure'] >= 100) & (df_era5['pressure'] <= 1000)]

    ax2.plot(df_era5_trop['temperature'], df_era5_trop['pressure'], 'o-',
             linewidth=2, markersize=5, color='red', label='ERA5', alpha=0.8)
    ax2.plot(df_meteo['temperature'], df_meteo['pressure'], 's-',
             linewidth=2, markersize=6, color='blue', label='Open-Meteo', alpha=0.8)

    ax2.set_xlabel('Temperature (°C)', fontsize=14)
    ax2.set_ylabel('Pressure (hPa)', fontsize=14)
    ax2.set_ylim(1000, 100)
    ax2.invert_yaxis()
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=12)
    ax2.set_title('Troposphere Comparison (100-1000 hPa)', fontsize=16, fontweight='bold')

    # Add climatology tropopause
    current_month = datetime.now().month
    tropopause_pressures = {
        1: 290, 2: 285, 3: 270, 4: 250, 5: 230, 6: 215,
        7: 210, 8: 215, 9: 230, 10: 250, 11: 270, 12: 285
    }
    trop_p_clim = tropopause_pressures.get(current_month, 250)
    ax2.axhline(y=trop_p_clim, color='green', linestyle=':', linewidth=2,
                label=f'Climatology: {trop_p_clim} hPa')
    ax2.legend(fontsize=11)

    plt.tight_layout()
    plt.savefig('era5_vs_openmeteo_comparison.png', dpi=150, bbox_inches='tight')
    print("[OK] Plot saved: era5_vs_openmeteo_comparison.png")

def main():
    print("\n" + "=" * 70)
    print("ERA5 vs OPEN-METEO TROPOPAUSE COMPARISON")
    print("Location: Rishiri Island (45.18°N, 141.24°E)")
    print("=" * 70)

    # Fetch ERA5 data
    era5_file, era5_date = fetch_era5_data()

    if era5_file is None:
        print("\n[NO] Failed to fetch ERA5 data. Check CDS API credentials.")
        print("  Setup guide: https://cds.climate.copernicus.eu/api-how-to")
        return

    df_era5 = process_era5_data(era5_file)

    # Fetch Open-Meteo data
    df_meteo, meteo_date = fetch_openmeteo_data()

    # Detect tropopause
    print("\n" + "=" * 70)
    print("TROPOPAUSE DETECTION")
    print("=" * 70)

    trop_p_era5, trop_h_era5 = detect_tropopause(df_era5)
    if trop_p_era5:
        print(f"\n[OK] ERA5 Tropopause detected:")
        print(f"  Pressure: {trop_p_era5:.0f} hPa")
        print(f"  Height: {trop_h_era5:.1f} km")
    else:
        print("\n[NO] ERA5 Tropopause NOT detected")

    trop_p_meteo, trop_h_meteo = detect_tropopause(df_meteo)
    if trop_p_meteo:
        print(f"\n[OK] Open-Meteo Tropopause detected:")
        print(f"  Pressure: {trop_p_meteo:.0f} hPa")
        print(f"  Height: {trop_h_meteo:.1f} km")
        print("  Note: This is likely a false positive (data doesn't extend high enough)")
    else:
        print("\n[NO] Open-Meteo Tropopause NOT detected (expected)")

    # Create visualization
    plot_comparison(df_era5, df_meteo, era5_date, meteo_date)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print("\n1. ERA5 Capabilities:")
    print(f"   - Vertical range: 1-1000 hPa (~48 km altitude)")
    print(f"   - Captures full stratosphere")
    print(f"   - Can detect true tropopause: {'YES' if trop_p_era5 else 'NO'}")

    print("\n2. Open-Meteo Capabilities:")
    print(f"   - Vertical range: 100-1000 hPa (~16 km altitude)")
    print(f"   - Troposphere only")
    print(f"   - Cannot detect true tropopause")

    print("\n3. Recommendation:")
    print("   For kelp drying forecast:")
    print("   - Open-Meteo is SUFFICIENT (LCL/LFC/EL in troposphere)")
    print("   - Add tropopause climatology as reference line only")
    print("\n   For advanced meteorology:")
    print("   - ERA5 provides true tropopause detection")
    print("   - But requires CDS API setup and slower data access")

    print("\n" + "=" * 70)
    print("COMPARISON COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
