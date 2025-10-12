"""Quick database check"""
import sqlite3
from database import DB_PATH

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("\n=== AMEDAS ACTUAL DATA ===")
cursor.execute("SELECT * FROM amedas_actual ORDER BY observation_date DESC LIMIT 5")
rows = cursor.fetchall()

if rows:
    print(f"Found {len(rows)} record(s)\n")
    for row in rows:
        print(f"Date: {row[1]}")
        print(f"  Temp Max: {row[2]}°C, Min: {row[3]}°C")
        print(f"  Humidity Min: {row[4]}%")
        print(f"  Wind Avg: {row[5]} m/s, Max: {row[6]} m/s")
        print(f"  Precipitation: {row[7]} mm")
        print(f"  Sunshine: {row[8]} h")
        print()
else:
    print("No data found")

print("\n=== FORECAST ARCHIVE DATA ===")
cursor.execute("SELECT COUNT(*) FROM forecast_archive")
forecast_count = cursor.fetchone()[0]
print(f"Total forecast records: {forecast_count}")

cursor.execute("SELECT DISTINCT forecast_date FROM forecast_archive ORDER BY forecast_date DESC LIMIT 3")
dates = cursor.fetchall()
if dates:
    print(f"Recent forecast dates: {', '.join(d[0] for d in dates)}")

conn.close()
