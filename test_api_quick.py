"""Quick API test script"""
import requests

# Test the inventory-trigger endpoint
url = "http://localhost:8000/inventory-trigger"
headers = {
    "X-API-Key": "dev-inventory-agent-2026",
    "Content-Type": "application/json"
}
data = {
    "product_id": "STEEL_SHEETS",
    "mode": "mock"
}

print("Testing /inventory-trigger endpoint...")
try:
    response = requests.post(url, json=data, headers=headers, timeout=30)
    print(f"Status Code: {response.status_code}")
    print(f"\nResponse:")
    print(response.json())
except Exception as e:
    print(f"Error: {e}")
