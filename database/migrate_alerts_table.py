#!/usr/bin/env python3
"""
Migration script to add handled, handled_at, and handled_by columns to alerts table.
"""

import sqlite3
import os
import sys

def migrate_alerts_table():
    """Add missing columns to alerts table if they don't exist."""
    
    # Get database path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, 'medibot.db')
    
    if not os.path.exists(db_path):
        print(f" Database not found at: {db_path}")
        return False
    
    print(f" Migrating database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check what columns currently exist
        cursor.execute("PRAGMA table_info(alerts)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"✓ Current columns in alerts table: {columns}")
        
        # Add handled column if it doesn't exist
        if 'handled' not in columns:
            print("  → Adding 'handled' column...")
            cursor.execute("""
                ALTER TABLE alerts ADD COLUMN handled INTEGER DEFAULT 0
            """)
            print("  ✓ Added 'handled' column")
        else:
            print("  ✓ Column 'handled' already exists")
        
        # Add handled_at column if it doesn't exist
        if 'handled_at' not in columns:
            print("  → Adding 'handled_at' column...")
            cursor.execute("""
                ALTER TABLE alerts ADD COLUMN handled_at DATETIME
            """)
            print("  ✓ Added 'handled_at' column")
        else:
            print("  ✓ Column 'handled_at' already exists")
        
        # Add handled_by column if it doesn't exist
        if 'handled_by' not in columns:
            print("  → Adding 'handled_by' column...")
            cursor.execute("""
                ALTER TABLE alerts ADD COLUMN handled_by TEXT
            """)
            print("  ✓ Added 'handled_by' column")
        else:
            print("  ✓ Column 'handled_by' already exists")
        
        # Add alert_type column if it doesn't exist
        if 'alert_type' not in columns:
            print("  → Adding 'alert_type' column...")
            cursor.execute("""
                ALTER TABLE alerts ADD COLUMN alert_type TEXT DEFAULT 'general'
            """)
            print("  ✓ Added 'alert_type' column")
        else:
            print("  ✓ Column 'alert_type' already exists")
        
        # Add severity column if it doesn't exist
        if 'severity' not in columns:
            print("  → Adding 'severity' column...")
            cursor.execute("""
                ALTER TABLE alerts ADD COLUMN severity TEXT DEFAULT 'medium'
            """)
            print("  ✓ Added 'severity' column")
        else:
            print("  ✓ Column 'severity' already exists")
        
        conn.commit()
        
        # ----- Nouvelle table : current_patient_session -----
        print("\n--- Migration current_patient_session ---")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS current_patient_session (
                id         INTEGER PRIMARY KEY DEFAULT 1,
                patient_id TEXT    NOT NULL,
                first_name TEXT,
                last_name  TEXT,
                identified_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  ✓ Table 'current_patient_session' prête")
        conn.commit()
        
        # Verify the migration
        cursor.execute("PRAGMA table_info(alerts)")
        new_columns = [row[1] for row in cursor.fetchall()]
        print(f"\n Migration complete! New columns: {new_columns}")
        
        # Show current alerts count
        cursor.execute("SELECT COUNT(*) FROM alerts")
        count = cursor.fetchone()[0]
        print(f" Database contains {count} alert(s)")
        
        # Show unhandled alerts count
        cursor.execute("SELECT COUNT(*) FROM alerts WHERE handled = 0")
        unhandled = cursor.fetchone()[0]
        print(f" Unhandled alerts: {unhandled}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f" Migration failed: {e}")
        return False


if __name__ == '__main__':
    print("="*60)
    print(" MediBot Database Migration")
    print("="*60)
    print()
    
    success = migrate_alerts_table()
    
    print()
    print("="*60)
    if success:
        print(" Migration completed successfully!")
    else:
        print(" Migration failed!")
        sys.exit(1)
    print("="*60)
