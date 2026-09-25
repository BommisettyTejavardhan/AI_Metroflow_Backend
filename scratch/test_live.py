import sys
import os
import requests
sys.path.append(os.path.abspath("."))
from backend.auth import create_access_token

token = create_access_token({"sub": "admin@metroflow.com", "role": "Admin"})
headers = {"Authorization": f"Bearer {token}"}

print("Testing live API...")
res = requests.get("http://127.0.0.1:8000/api/stations/network-map")
print("Network Map Status:", res.status_code)
print("Network Map Count:", len(res.json().get("stations", [])))
