"""Use Starlette TestClient to hit /openapi.json and capture errors."""
import traceback

try:
    from starlette.testclient import TestClient
    from app.main import app

    print("Starting TestClient...")
    with TestClient(app, raise_server_exceptions=True) as client:
        print("Hitting /openapi.json ...")
        try:
            response = client.get("/openapi.json")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                import json
                data = response.json()
                print("Success! Paths:", list(data.get("paths", {}).keys()))
            else:
                print("Error body:", response.text[:2000])
        except Exception as e:
            print("Exception during request:")
            traceback.print_exc()
except Exception:
    print("Setup error:")
    traceback.print_exc()
