"""Test the demo/simulate endpoint"""
import requests
import json

try:
    print("Testing http://localhost:8002/api/demo/simulate...")
    response = requests.get("http://localhost:8002/api/demo/simulate", timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Success! Got {len(data.get('predictions', []))} predictions")
        print(f"  Network risk: {data.get('network_risk_score', 0):.2%}")
    else:
        print(f"✗ Error: {response.text}")
except Exception as e:
    print(f"✗ Failed: {e}")
