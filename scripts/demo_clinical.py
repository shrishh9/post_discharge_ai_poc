import requests
import json
import sys

API_URL = "http://localhost:8000"

def run_demo():
    # 1. Get a patient ID (John Smith)
    print("1. Finding Patient John Smith...")
    res = requests.get(f"{API_URL}/patient?name=John Smith")
    if res.status_code != 200:
        print("Could not find John Smith. Run generate_dummy_patients.py first.")
        return
    
    patient = res.json()
    if isinstance(patient, list):
        patient = patient[0] # Handle multiple matches logic if needed
        
    patient_id = patient["patient_id"]
    print(f"Found Patient ID: {patient_id}")
    
    # 2. Start Session
    res = requests.post(f"{API_URL}/session/start")
    session_id = res.json()["session_id"]
    
    # 3. Ask Clinical Question
    question = "I have swelling in my legs — what could this mean after discharge?"
    print(f"\n2. Asking Clinical Question: '{question}'")
    
    res = requests.post(f"{API_URL}/agent/clinical", json={
        "session_id": session_id,
        "patient_id": patient_id,
        "question": question
    })
    
    if res.status_code == 200:
        data = res.json()
        print("\nResponse:")
        print(json.dumps(data, indent=2))
        
        if data["source_type"] == "KB":
            print("\nSUCCESS: Answered from KB.")
        else:
            print(f"\nNote: Source type is {data['source_type']}")
    else:
        print("Error:", res.text)

if __name__ == "__main__":
    run_demo()
