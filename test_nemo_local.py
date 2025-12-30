import os
import json

import requests

from dotenv import load_dotenv
load_dotenv()

BASE_URL = os.getenv("NEMO_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("NEMO_API_KEY")

if not API_KEY:
    raise SystemExit("NEMO_API_KEY is not set in the environment")

url = f"{BASE_URL}/data-designer/v1/generate"

payload = {
    "table_name": "TestTable",
    "num_rows": 5,
    "config": {
        "columns": [
            {"name": "id", "type": "string", "generator": "uuid"},
            {"name": "amount", "type": "float"},
        ]
    },
}

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

print(f"POST {url}")
resp = requests.post(url, json=payload, headers=headers, timeout=60)
print("Status:", resp.status_code)

try:
    data = resp.json()
except json.JSONDecodeError:
    print("Non-JSON response body:")
    print(resp.text)
else:
    print("Response JSON:")
    print(json.dumps(data, indent=2))
