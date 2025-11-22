import sqlite3
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

DB_PATH = "patients.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            patient_name TEXT,
            discharge_date TEXT,
            primary_diagnosis TEXT,
            medications TEXT,
            follow_up TEXT,
            warning_signs TEXT,
            discharge_instructions TEXT,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()

def create_patient(record: Dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO patients (
                patient_id, patient_name, discharge_date, primary_diagnosis, 
                medications, follow_up, warning_signs, discharge_instructions, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record['patient_id'],
            record['patient_name'],
            record['discharge_date'],
            record['primary_diagnosis'],
            json.dumps(record['medications']),
            record['follow_up'],
            json.dumps(record['warning_signs']),
            record['discharge_instructions'],
            record['notes']
        ))
        conn.commit()
    except Exception as e:
        logger.error(f"Error creating patient: {e}")
    finally:
        conn.close()

def find_patient_by_name(name: str) -> List[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    # Simple fuzzy search using LIKE
    cursor.execute("SELECT * FROM patients WHERE patient_name LIKE ?", (f"%{name}%",))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        res = dict(row)
        # Parse JSON fields
        try:
            res['medications'] = json.loads(res['medications'])
        except:
            pass
        try:
            res['warning_signs'] = json.loads(res['warning_signs'])
        except:
            pass
        results.append(res)
    return results

def get_patient_by_id(patient_id: str) -> Optional[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        res = dict(row)
        try:
            res['medications'] = json.loads(res['medications'])
        except:
            pass
        try:
            res['warning_signs'] = json.loads(res['warning_signs'])
        except:
            pass
        return res
    return None

def list_patients():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT patient_id, patient_name FROM patients")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Initialize DB on module load (or can be explicit)
init_db()
