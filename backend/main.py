import logging
from logging.handlers import RotatingFileHandler
import uuid
import os
from typing import Optional, List, Dict
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.patient_db import find_patient_by_name, list_patients
from backend.langgraph_agents import run_receptionist_flow, run_clinical_flow, search_web_tool

# Setup Logging
LOG_FILE = "./logs/app.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=1000000, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("api")

app = FastAPI(title="Post-Discharge Medical AI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class SessionStartResponse(BaseModel):
    session_id: str
    message: str

class MessageRequest(BaseModel):
    session_id: str
    message: str

class ClinicalRequest(BaseModel):
    session_id: str
    patient_id: str
    question: str

class AgentResponse(BaseModel):
    answer_text: str
    sources: List[Dict] = []
    source_type: str
    session_id: str
    timestamp: Optional[str] = None

# In-memory session store for history (simple)
sessions = {}

@app.post("/session/start", response_model=SessionStartResponse)
def start_session():
    session_id = str(uuid.uuid4())
    sessions[session_id] = {"history": [], "patient_id": None}
    logger.info(f"Session started: {session_id}")
    return {"session_id": session_id, "message": "Session initialized."}

@app.get("/patient")
def get_patient(name: str = Query(...)):
    logger.info(f"Searching for patient: {name}")
    results = find_patient_by_name(name)
    if not results:
        raise HTTPException(status_code=404, detail="Patient not found")
    if len(results) > 1:
        # For simplicity, return list but warn
        return {"status": "multiple_matches", "matches": results}
    return results[0]

@app.post("/agent/receptionist")
def agent_receptionist(req: MessageRequest):
    logger.info(f"Receptionist Agent called. Session: {req.session_id}, Message: {req.message}")
    
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
        
    history = sessions[req.session_id]["history"]
    
    # Get current patient context if any
    patient_id = sessions[req.session_id].get("patient_id")
    patient_record = None
    if patient_id:
        from backend.patient_db import get_patient_by_id
        patient_record = get_patient_by_id(patient_id)

    response = run_receptionist_flow(req.session_id, req.message, patient_record, history)
    
    # Update history
    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": response['answer_text']})
    
    
    return {
        "answer_text": response['answer_text'],
        "sources": response.get('sources', []),
        "source_type": response.get('source_type', 'System'),
        "session_id": req.session_id,
        "timestamp": "2025-11-20T12:00:00+05:30" # Mock timestamp
    }

@app.post("/agent/clinical")
def agent_clinical(req: ClinicalRequest):
    logger.info(f"Clinical Agent called. Session: {req.session_id}, Patient: {req.patient_id}, Q: {req.question}")
    
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
        
    history = sessions[req.session_id]["history"]
    
    response = run_clinical_flow(req.session_id, req.question, req.patient_id, history)
    
    history.append({"role": "user", "content": req.question})
    history.append({"role": "assistant", "content": response['answer_text']})
    
    return {
        "answer_text": response['answer_text'],
        "sources": response.get('sources', []),
        "source_type": response.get('source_type', 'KB'),
        "session_id": req.session_id,
        "timestamp": "2025-11-20T12:00:00+05:30"
    }

@app.post("/search/web")
def search_web(query: str):
    logger.info(f"Web search requested: {query}")
    results = search_web_tool(query)
    return {"results": results, "source_type": "Web"}

@app.get("/logs")
def get_logs(session_id: Optional[str] = None):
    # Read logs from file
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
        # Filter by session_id if provided (simple string match)
        if session_id:
            lines = [l for l in lines if session_id in l]
        return {"logs": lines[-100:]} # Return last 100 lines
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
