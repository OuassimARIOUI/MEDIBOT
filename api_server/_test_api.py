"""Quick test of the /api/alerts/unhandled endpoint."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()
print("DB:", app.config['DATABASE_PATH'])

client = app.test_client()

# Test /api/alerts/unhandled
r = client.get('/api/alerts/unhandled')
data = r.get_json()
print(f"\n--- /api/alerts/unhandled ---")
print(f"Status: {r.status_code}")
print(f"Success: {data.get('success')}")
print(f"Count: {data.get('count')}")
if data.get('error'):
    print(f"ERROR: {data['error']}")
for a in data.get('alerts', [])[:5]:
    print(f"  #{a['id']} [{a['severity']}] {a.get('patient_name','?')} - Ch.{a.get('room_number','?')} - {a['message'][:60]}")

# Test /api/alerts/stats
r2 = client.get('/api/alerts/stats')
data2 = r2.get_json()
print(f"\n--- /api/alerts/stats ---")
print(f"Stats: {data2.get('stats')}")
