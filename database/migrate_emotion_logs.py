#!/usr/bin/env python3
"""
Migration script to add the emotion_logs table to medibot.db.
Run this once to add the table to an existing database.
"""

import sqlite3
import os
import sys


def migrate_emotion_logs():
    """Add emotion_logs table if it doesn't exist."""

    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, 'medibot.db')

    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found at: {db_path}")
        return False

    print(f"[MIGRATION] Migrating database: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if emotion_logs table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='emotion_logs'
        """)
        if cursor.fetchone():
            print("  ✓ Table 'emotion_logs' already exists, skipping.")
            conn.close()
            return True

        # Create the emotion_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emotion_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                emotion TEXT NOT NULL,
                severity TEXT DEFAULT 'low',
                detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
            )
        """)

        conn.commit()
        print("  [OK] Table 'emotion_logs' created successfully!")

        # Verify
        cursor.execute("PRAGMA table_info(emotion_logs)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"  [OK] Columns: {columns}")

        conn.close()
        return True

    except Exception as e:
        print(f"  [ERROR] Migration failed: {e}")
        return False


if __name__ == '__main__':
    print("=" * 60)
    print("MediBot -- Migration emotion_logs")
    print("=" * 60)
    print()

    success = migrate_emotion_logs()

    print()
    print("=" * 60)
    if success:
        print("[OK] Migration completed successfully!")
    else:
        print("[ERROR] Migration failed!")
        sys.exit(1)
    print("=" * 60)
