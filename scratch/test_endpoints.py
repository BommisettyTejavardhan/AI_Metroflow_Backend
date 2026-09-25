import asyncio
import sys
import os
sys.path.append(os.path.abspath("."))
from fastapi.testclient import TestClient
from backend.main import app
from backend.auth import create_access_token

client = TestClient(app)

# Create a mock token for an Admin user
token = create_access_token({"sub": "admin@metroflow.com", "role": "Admin"})
headers = {"Authorization": f"Bearer {token}"}

print("Running Endpoint Checks...")

# 1. Test AI Prediction (Predict Crowd)
print("\n--- Testing /api/predictions/predict-crowd ---")
res = client.post("/api/predictions/predict-crowd", json={
    "station": "Jhil Mil",
    "date": "2026-07-15",
    "time": "08:30"
}, headers=headers)
print("Status:", res.status_code)
if res.status_code != 200:
    print("Response:", res.text)

# 2. Test Passenger Forecast
print("\n--- Testing /api/predictions/forecast-demand ---")
res = client.post("/api/predictions/forecast-demand", json={
    "station": "Jhil Mil",
    "timeframe": "hourly"
}, headers=headers)
print("Status:", res.status_code)
if res.status_code != 200:
    print("Response:", res.text)

# 3. Test Scheduling (Routes)
print("\n--- Testing /api/schedules/routes ---")
res = client.get("/api/schedules/routes", headers=headers)
print("Status:", res.status_code)
if res.status_code != 200:
    print("Response:", res.text)

# 4. Test Frequency Optimization
print("\n--- Testing /api/schedules/optimize-frequency ---")
# Need a route_id to test
routes = res.json()
if routes:
    route_id = routes[0].get("id")
    res = client.post("/api/schedules/optimize-frequency", json={
        "route_id": route_id,
        "target_interval_minutes": 5
    }, headers=headers)
    print("Status:", res.status_code)
    if res.status_code != 200:
        print("Response:", res.text)
else:
    print("No routes found, skipping optimization test")

# 5. Test Analytics Reports
print("\n--- Testing /api/reports/analytics/passenger-trends ---")
res = client.get("/api/reports/analytics/passenger-trends", headers=headers)
print("Status:", res.status_code)
if res.status_code != 200:
    print("Response:", res.text)

print("\nAll tests completed.")
