"""
Find correct JMA Amedas station ID for Kutsugata, Rishiri Island
"""
import requests
import json
import sys
import io

# Windows console encoding fix
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def find_kutsugata_id():
    """Search for Kutsugata station ID from JMA Amedas master file"""

    url = "https://www.jma.go.jp/bosai/amedas/const/amedastable.json"

    print("Fetching JMA Amedas master file...")
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return

    stations = response.json()

    print(f"\nTotal Amedas stations in Japan: {len(stations)}\n")

    print("=" * 80)
    print("Amedas stations in Rishiri Island / Wakkanai area:")
    print("=" * 80)

    kutsugata_candidates = []

    for station_id, station_info in stations.items():
        name = station_info.get('kjName', '')
        lat = station_info.get('lat', [None, None])
        lon = station_info.get('lon', [None, None])

        # Convert lat/lon from [degrees, minutes] to decimal degrees
        if lat[0] is not None and lon[0] is not None:
            lat_deg = lat[0] + lat[1] / 60.0
            lon_deg = lon[0] + lon[1] / 60.0

            # Rishiri Island area (Lat 45.0-45.5, Lon 141.0-141.5)
            if 45.0 <= lat_deg <= 45.5 and 141.0 <= lon_deg <= 141.5:
                print(f"\nStation: {name}")
                print(f"  ID: {station_id}")
                print(f"  Coordinates: {lat_deg:.6f}N, {lon_deg:.6f}E")

                # Get elevation (elems can be dict or other type)
                elems = station_info.get('elems', {})
                if isinstance(elems, dict):
                    elevation = elems.get('altitude', 'N/A')
                else:
                    elevation = 'N/A'
                print(f"  Elevation: {elevation}m")

                # Check if it's Kutsugata
                if 'kutsugata' in name or 'くつがた' in name.lower():
                    kutsugata_candidates.append({
                        'id': station_id,
                        'name': name,
                        'lat': lat_deg,
                        'lon': lon_deg,
                        'info': station_info
                    })
                    print("  *** LIKELY KUTSUGATA ***")

    print("\n" + "=" * 80)
    print("Kutsugata candidate details:")
    print("=" * 80)

    if kutsugata_candidates:
        for candidate in kutsugata_candidates:
            print(f"\n[CANDIDATE] {candidate['name']}")
            print(f"  Amedas ID: {candidate['id']}")
            print(f"  Coordinates: {candidate['lat']:.8f}N, {candidate['lon']:.8f}E")
            print(f"  Reference (Expected Kutsugata): 45.17840444N, 141.13954051E")

            # Calculate distance (approximate)
            lat_diff = abs(candidate['lat'] - 45.17840444)
            lon_diff = abs(candidate['lon'] - 141.13954051)
            distance_approx = ((lat_diff * 111) ** 2 + (lon_diff * 111 * 0.7) ** 2) ** 0.5
            print(f"  Distance from expected location: ~{distance_approx:.2f} km")

            # Check observation elements
            elems = candidate['info'].get('elems', {})
            print(f"  Observation elements:")
            print(f"    Temperature: {'Yes' if 'temp' in elems else 'No'}")
            print(f"    Humidity: {'Yes' if 'humidity' in elems else 'No'}")
            print(f"    Wind: {'Yes' if 'wind' in elems else 'No'}")
            print(f"    Precipitation: {'Yes' if 'precipitation' in elems else 'No'}")
            print(f"    Sunshine: {'Yes' if 'sun' in elems else 'No'}")

            # Test data fetch
            print(f"\n  Data fetch test:")
            test_url = f"https://www.jma.go.jp/bosai/amedas/data/point/{candidate['id']}/20251003.json"
            test_response = requests.get(test_url)
            print(f"    URL: {test_url}")
            print(f"    Status: {test_response.status_code}")
            if test_response.status_code == 200:
                print(f"    SUCCESS - This is the correct ID!")
            else:
                print(f"    FAILED")
    else:
        print("\nNo station named 'Kutsugata' found.")
        print("Manual selection from nearby stations required.")

    return kutsugata_candidates

if __name__ == '__main__':
    candidates = find_kutsugata_id()

    if candidates:
        print("\n" + "=" * 80)
        print("CONCLUSION:")
        print("=" * 80)
        for c in candidates:
            print(f"Amedas Kutsugata ID: {c['id']}")
            print(f"Update config.py:")
            print(f"  AMEDAS_KUTSUGATA['id'] = '{c['id']}'")
