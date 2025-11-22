import json
import uuid
import random
import datetime
from backend.patient_db import create_patient

# Data pools
FIRST_NAMES = ["John", "Jane", "Michael", "Emily", "David", "Sarah", "Robert", "Jessica", "William", "Ashley", "James", "Mary", "Richard", "Patricia", "Joseph", "Linda", "Thomas", "Barbara", "Charles", "Elizabeth", "Daniel", "Jennifer", "Matthew", "Maria", "Anthony", "Susan"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris"]

DIAGNOSES = [
    "Acute on chronic kidney disease",
    "End-stage renal disease",
    "Nephrotic syndrome",
    "Acute kidney injury",
    "Hypertensive nephrosclerosis",
    "Diabetic nephropathy",
    "Polycystic kidney disease",
    "Glomerulonephritis",
    "Pyelonephritis",
    "Renal artery stenosis"
]

MEDICATIONS = [
    "Lisinopril 10mg daily",
    "Furosemide 40mg daily",
    "Amlodipine 5mg daily",
    "Metoprolol 25mg BID",
    "Prednisone 10mg daily",
    "Mycophenolate mofetil 500mg BID",
    "Tacrolimus 1mg BID",
    "Sevelamer 800mg TID with meals",
    "Calcitriol 0.25mcg daily",
    "Erythropoietin 4000 units weekly"
]

WARNING_SIGNS = [
    "Swelling in legs or ankles",
    "Shortness of breath",
    "Decreased urine output",
    "Weight gain > 2kg in 2 days",
    "Fever > 100.4F",
    "Blood in urine",
    "Severe flank pain",
    "Confusion or lethargy"
]

INSTRUCTIONS = [
    "Monitor daily weight.",
    "Low sodium diet (2g/day).",
    "Fluid restriction 1.5L/day.",
    "Avoid NSAIDs.",
    "Monitor blood pressure daily.",
    "Follow up with nephrology in 2 weeks.",
    "Take medications as prescribed."
]

def generate_patient():
    name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    # Ensure unique names for this small set if possible, but random is fine.
    
    diagnosis = random.choice(DIAGNOSES)
    meds = random.sample(MEDICATIONS, k=random.randint(2, 5))
    warnings = random.sample(WARNING_SIGNS, k=random.randint(2, 4))
    
    discharge_date = (datetime.date.today() - datetime.timedelta(days=random.randint(1, 30))).isoformat()
    
    record = {
        "patient_id": str(uuid.uuid4()),
        "patient_name": name,
        "discharge_date": discharge_date,
        "primary_diagnosis": diagnosis,
        "medications": meds,
        "follow_up": "2 weeks",
        "warning_signs": warnings,
        "discharge_instructions": " ".join(random.sample(INSTRUCTIONS, k=3)),
        "notes": f"Patient discharged in stable condition. {diagnosis} managed."
    }
    return record

def main():
    patients = []
    # Generate 30 patients
    for _ in range(30):
        p = generate_patient()
        patients.append(p)
        create_patient(p)
        
    # Ensure specific demo patient exists
    demo_patient = {
        "patient_id": str(uuid.uuid4()),
        "patient_name": "John Smith",
        "discharge_date": "2024-01-15",
        "primary_diagnosis": "Acute on chronic kidney disease",
        "medications": ["Lisinopril 10mg", "Furosemide 40mg"],
        "follow_up": "1 week",
        "warning_signs": ["Swelling", "Shortness of breath"],
        "discharge_instructions": "Monitor weight daily. Low salt diet.",
        "notes": "Patient stable."
    }
    patients.append(demo_patient)
    create_patient(demo_patient)
    
    with open("patients.json", "w") as f:
        json.dump(patients, f, indent=2)
        
    print(f"Generated {len(patients)} patients and saved to patients.json and SQLite DB.")

if __name__ == "__main__":
    main()
