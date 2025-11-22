import streamlit as st
import requests
import json
import uuid
from datetime import datetime

# Config
import os
API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Post-Discharge Medical AI Assistant", layout="wide")

# CSS for badges
st.markdown("""
<style>
.badge-kb {
    background-color: #d4edda;
    color: #155724;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.8em;
    border: 1px solid #c3e6cb;
}
.badge-web {
    background-color: #fff3cd;
    color: #856404;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.8em;
    border: 1px solid #ffeeba;
}
.badge-system {
    background-color: #e2e3e5;
    color: #383d41;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.8em;
    border: 1px solid #d6d8db;
}
.disclaimer {
    background-color: #f8d7da;
    color: #721c24;
    padding: 10px;
    border-radius: 5px;
    margin-bottom: 20px;
    text-align: center;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# Disclaimer
st.markdown('<div class="disclaimer">This is educational only. Consult a healthcare professional for medical advice.</div>', unsafe_allow_html=True)

st.title("Post-Discharge Medical AI Assistant")

# Session State
if "session_id" not in st.session_state:
    try:
        res = requests.post(f"{API_URL}/session/start")
        if res.status_code == 200:
            st.session_state.session_id = res.json()["session_id"]
            st.session_state.messages = []
            st.session_state.patient = None
        else:
            st.error("Failed to start session backend.")
    except Exception as e:
        st.error(f"Backend not reachable: {e}")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar - Patient Lookup & Logs
with st.sidebar:
    st.header("Patient Context")
    
    # Patient Lookup
    patient_name_input = st.text_input("Patient Name Lookup")
    if st.button("Find Patient"):
        if patient_name_input:
            # We can use the receptionist agent to find the patient or the direct endpoint.
            # The prompt says "Input: patient name entry (for receptionist)".
            # Let's send a message to receptionist.
            
            # Add user message
            st.session_state.messages.append({"role": "user", "content": patient_name_input})
            
            try:
                res = requests.post(f"{API_URL}/agent/receptionist", json={
                    "session_id": st.session_state.session_id,
                    "message": patient_name_input
                })
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": data["answer_text"],
                        "sources": data.get("sources", []),
                        "source_type": data.get("source_type")
                    })
                    
                    # Check if we can fetch patient details now
                    # We'll try to fetch patient details directly to populate the sidebar
                    # if the name matches.
                    try:
                        pat_res = requests.get(f"{API_URL}/patient?name={patient_name_input}")
                        if pat_res.status_code == 200:
                            st.session_state.patient = pat_res.json()
                    except:
                        pass
                        
                else:
                    st.error("Error contacting receptionist.")
            except Exception as e:
                st.error(f"Error: {e}")

    # Display Patient Info
    if st.session_state.get("patient"):
        p = st.session_state.patient
        with st.expander("Patient Record", expanded=True):
            st.write(f"**Name:** {p['patient_name']}")
            st.write(f"**ID:** {p['patient_id']}")
            st.write(f"**Discharge:** {p['discharge_date']}")
            st.write(f"**Diagnosis:** {p['primary_diagnosis']}")
            st.write("**Medications:**")
            st.write(p['medications'])
            st.write("**Warning Signs:**")
            st.write(p['warning_signs'])
            
    st.divider()
    
    # Logs
    if st.button("View Logs"):
        try:
            res = requests.get(f"{API_URL}/logs?session_id={st.session_state.session_id}")
            if res.status_code == 200:
                logs = res.json().get("logs", [])
                st.text_area("Logs", "".join(logs), height=300)
        except:
            st.error("Could not fetch logs.")

# Main Chat
chat_container = st.container()

with chat_container:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
            # Show sources/badges for assistant
            if msg["role"] == "assistant":
                stype = msg.get("source_type", "System")
                badge_class = "badge-system"
                if stype == "KB": badge_class = "badge-kb"
                elif stype == "Web": badge_class = "badge-web"
                
                st.markdown(f'<span class="{badge_class}">{stype}</span>', unsafe_allow_html=True)
                
                if msg.get("sources"):
                    with st.expander("Sources"):
                        for s in msg["sources"]:
                            if "page" in s:
                                st.write(f"- **KB**: Page {s['page']} (Score: {s.get('score', 'N/A')})")
                            elif "url" in s:
                                st.write(f"- **Web**: [{s['title']}]({s['url']})")

# Chat Input
user_input = st.chat_input("Ask a clinical question...")

if user_input:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Decide which agent to call
    # If we have a patient, we might default to Clinical, but Receptionist can route.
    # The prompt says "Input: ... free text (for clinical queries)".
    # If we have a patient, we assume clinical intent for the main chat input?
    # Or we send to Receptionist to route?
    # Let's send to Receptionist first as it's the entry point, unless we are sure.
    # Actually, the prompt says: "POST /agent/clinical ... accepts {session_id, patient_id, question}".
    # If we have a patient_id, we can call clinical directly if we want to force RAG.
    # Let's try to be smart: if patient is loaded, call Clinical. Else Receptionist.
    
    target_agent = "receptionist"
    payload = {"session_id": st.session_state.session_id, "message": user_input}
    
    if st.session_state.get("patient"):
        target_agent = "clinical"
        payload = {
            "session_id": st.session_state.session_id, 
            "patient_id": st.session_state.patient["patient_id"],
            "question": user_input
        }
    
    try:
        res = requests.post(f"{API_URL}/agent/{target_agent}", json=payload)
        if res.status_code == 200:
            data = res.json()
            st.session_state.messages.append({
                "role": "assistant", 
                "content": data["answer_text"],
                "sources": data.get("sources", []),
                "source_type": data.get("source_type")
            })
            st.rerun()
        else:
            st.error(f"Error from {target_agent}: {res.text}")
    except Exception as e:
        st.error(f"Error: {e}")
