import requests
import json
import sys

API_URL = "http://localhost:8000"

def run_test():
    print("1. Starting Session...")
    res = requests.post(f"{API_URL}/session/start")
    if res.status_code != 200:
        print("Failed to start session")
        return
    session_id = res.json()["session_id"]
    print(f"Session ID: {session_id}")
    
    print("\n2. Sending Greeting with Name 'John Smith'...")
    res = requests.post(f"{API_URL}/agent/receptionist", json={
        "session_id": session_id,
        "message": "Hi, my name is John Smith."
    })
    
    if res.status_code == 200:
        data = res.json()
        print("Response:", json.dumps(data, indent=2))
        if "Found report" in data["answer_text"] or "John Smith" in data["answer_text"]:
            print("SUCCESS: Patient found.")
        else:
            print("WARNING: Patient might not have been found.")
    else:
        print("Error:", res.text)

if __name__ == "__main__":
    run_test()
