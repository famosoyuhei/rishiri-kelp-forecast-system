"""
Database schema and utilities for forecast accuracy analysis
"""

import sqlite3
from datetime import datetime
import os

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'forecast_accuracy.db')

def init_database():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table 1: forecast_archive
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS forecast_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spot_name TEXT NOT NULL,
            forecast_date DATE NOT NULL,
            target_date DATE NOT NULL,
            days_ahead INTEGER NOT NULL,
            temp_max REAL,
            temp_min REAL,
            humidity_min REAL,
            wind_speed_avg REAL,
            precipitation REAL,
            drying_score REAL,
            risk_level TEXT,
            forecast_data_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(spot_name, forecast_date, target_date)
        )
    ''')

    # Index for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_forecast_target
        ON forecast_archive(target_date, days_ahead)
    ''')

    # Table 2: amedas_actual
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS amedas_actual (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            observation_date DATE NOT NULL UNIQUE,
            temp_max REAL,
            temp_min REAL,
            humidity_min REAL,
            wind_speed_avg REAL,
            wind_speed_max REAL,
            precipitation REAL,
            sunshine_hours REAL,
            amedas_data_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table 3: accuracy_analysis
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accuracy_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_date DATE NOT NULL,
            spot_name TEXT NOT NULL,
            target_date DATE NOT NULL,
            days_ahead INTEGER NOT NULL,
            temp_max_error REAL,
            temp_min_error REAL,
            humidity_error REAL,
            wind_error REAL,
            precipitation_forecast REAL,
            precipitation_actual REAL,
            precipitation_hit BOOLEAN,
            drying_forecast_score REAL,
            drying_possible_forecast BOOLEAN,
            drying_possible_actual BOOLEAN,
            forecast_correct BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(spot_name, target_date, days_ahead)
        )
    ''')

    # Index for analysis queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_analysis_days
        ON accuracy_analysis(days_ahead, target_date)
    ''')

    conn.commit()
    conn.close()

    print(f"Database initialized: {DB_PATH}")

def get_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)

if __name__ == '__main__':
    init_database()
    print("✓ Database schema created successfully")
