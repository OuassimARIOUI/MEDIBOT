"""One-time script to set severity on existing alerts."""
import sqlite3, os

db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "medibot.db")
conn = sqlite3.connect(db)
c = conn.cursor()

# Mark emergency alerts
c.execute("""
    UPDATE alerts SET severity='high', alert_type='emergency'
    WHERE message LIKE '%URGENCE%' OR message LIKE '%urgence%' OR message LIKE '%SOS%'
""")
print(f"Updated {c.rowcount} emergency alerts to severity=high")

# Default the rest
c.execute("""
    UPDATE alerts SET severity='medium', alert_type='general'
    WHERE severity IS NULL
""")
print(f"Updated {c.rowcount} other alerts to severity=medium")

conn.commit()

# Show results
c.execute("SELECT alert_id, severity, alert_type, handled, substr(message,1,70) FROM alerts")
for r in c.fetchall():
    print(r)

conn.close()
print("Done.")
