import logging
import json
from typing import Dict, Any, List, Optional, TypedDict
from langgraph.graph import StateGraph, END
from backend.patient_db import find_patient_by_name, create_patient
from backend.rag import retrieve, generate_answer
from backend.grok_wrapper import grok_generate
from backend.prompts import RECEPTIONIST_SYSTEM_PROMPT, CLINICAL_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Define State
class AgentState(TypedDict):
    session_id: str
    messages: List[Dict[str, str]]  # role, content
    user_input: str
    patient_id: Optional[str]
    patient_record: Optional[Dict[str, Any]]
    agent_response: Optional[Dict[str, Any]]
    next_step: Optional[str] # 'clinical', 'end', 'web_search'

# Mock Web Search Tool
def search_web_tool(query: str) -> List[Dict[str, Any]]:
    # In a real app, this would call Google/Bing API
    # For POC, we return a stub as requested
    return [
        {
            "title": "Latest Guidelines on Post-Discharge Nephrology Care",
            "snippet": "Recent studies suggest monitoring weight daily is crucial...",
            "url": "https://medical-journal.example.com/nephrology"
        }
    ]

# Nodes
def receptionist_node(state: AgentState) -> AgentState:
    user_input = state['user_input']
    messages = state['messages']
    patient_record = state.get('patient_record')
    # Quick greeting handler: if user says hi/hello, respond immediately with a greeting
    # and echo the user input so frontend can show what triggered the greeting.
    greeting_tokens = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
    if user_input and user_input.strip().lower() in greeting_tokens:
        response_text = f"Hello! I received: '{user_input.strip()}'. I'm the Post-Discharge Assistant — please provide a patient name or ask a clinical question."
        state['agent_response'] = {
            "answer_text": response_text,
            "source_type": "System",
            "sources": []
        }
        return state
    
    # Simple logic to detect intent or use LLM to decide.
    # For this POC, we'll use a mix of heuristic and LLM.
    
    # Check if we are looking for a patient
    if not patient_record:
        # Heuristic: assume input is a name if it's short and we don't have a patient
        # Or use LLM to extract name.
        # Let's try to find patient by name using the input as the name query
        # if the previous message asked for a name.
        
        # But the prompt says "Receptionist agent handles greetings, asks for patient name".
        # We will use Grok to process the input and decide what to do.
        
        system_prompt = RECEPTIONIST_SYSTEM_PROMPT
        prompt = f"{system_prompt}\n\nCurrent Conversation:\n{json.dumps(messages[-3:])}\n\nUser Input: {user_input}\n\nTask: Analyze input. If it's a name, extract it. If it's a clinical question, identify it. Return JSON: {{'action': 'lookup_patient'|'ask_name'|'handoff_clinical'|'chat', 'name': '...', 'response_text': '...'}}"
        
        # Using Grok to decide action
        try:
            llm_response = grok_generate(prompt)
            # Attempt to parse JSON. Grok might not return perfect JSON. 
            # We'll add a fallback.
            # For the POC, let's try to be robust.
            if "{" in llm_response and "}" in llm_response:
                json_str = llm_response[llm_response.find("{"):llm_response.rfind("}")+1]
                decision = json.loads(json_str)
            else:
                # Fallback logic
                if len(user_input.split()) < 5:
                    decision = {"action": "lookup_patient", "name": user_input}
                else:
                    decision = {"action": "chat", "response_text": llm_response}
        except:
             decision = {"action": "chat", "response_text": "Could you please repeat that?"}

        if decision.get('action') == 'lookup_patient':
            name = decision.get('name', user_input)
            patients = find_patient_by_name(name)
            if patients:
                # Found
                patient = patients[0] # Take first for now
                state['patient_record'] = patient
                state['patient_id'] = patient['patient_id']
                
                summary = f"Found report dated {patient['discharge_date']}. Diagnosis: {patient['primary_diagnosis']}. Meds: {patient['medications']}."
                follow_up = "Are you experiencing swelling or reduced urine output?"
                response_text = f"{summary} {follow_up}"
                
                state['agent_response'] = {
                    "answer_text": response_text,
                    "source_type": "System",
                    "sources": []
                }
            else:
                state['agent_response'] = {
                    "answer_text": f"I couldn't find a patient named {name}. Could you please check the spelling?",
                    "source_type": "System",
                    "sources": []
                }
        elif decision.get('action') == 'handoff_clinical':
            state['next_step'] = 'clinical'
            return state
        else:
            state['agent_response'] = {
                "answer_text": decision.get('response_text', "How can I help you?"),
                "source_type": "System",
                "sources": []
            }
            
    else:
        # We have a patient. Check if input is clinical or triage.
        # If user says "swelling", "pain", etc -> Triage or Clinical.
        # Receptionist handles triage (urgent vs non-urgent) then hands off if clinical question.
        
        prompt = f"{RECEPTIONIST_SYSTEM_PROMPT}\n\nPatient Context: {json.dumps(patient_record)}\nUser Input: {user_input}\n\nDetermine if this is an urgent triage situation, a general clinical question, or small talk. Return JSON: {{'type': 'urgent'|'clinical'|'chat', 'response': '...'}}"
        
        try:
            llm_response = grok_generate(prompt)
            if "{" in llm_response:
                json_str = llm_response[llm_response.find("{"):llm_response.rfind("}")+1]
                analysis = json.loads(json_str)
            else:
                # Fallback
                if "swelling" in user_input.lower() or "pain" in user_input.lower():
                    analysis = {"type": "clinical"}
                else:
                    analysis = {"type": "chat", "response": llm_response}
        except:
            analysis = {"type": "chat", "response": "I see."}
            
        if analysis.get('type') == 'urgent':
            # Log urgent
            logger.warning(f"URGENT EVENT: Session {state['session_id']} - {user_input}")
            state['agent_response'] = {
                "answer_text": analysis.get('response', "Please go to the nearest emergency room immediately."),
                "source_type": "System",
                "sources": []
            }
        elif analysis.get('type') == 'clinical':
            state['next_step'] = 'clinical'
        else:
            state['agent_response'] = {
                "answer_text": analysis.get('response', "Okay."),
                "source_type": "System",
                "sources": []
            }

    return state

def clinical_node(state: AgentState) -> AgentState:
    user_input = state['user_input']
    patient_record = state.get('patient_record')
    
    # 1. Retrieve
    # Construct query with patient context if possible
    query = user_input
    if patient_record:
        query = f"{user_input} (Patient Diagnosis: {patient_record.get('primary_diagnosis')})"
        
    retrieved = retrieve(query)
    
    # 2. Generate
    result = generate_answer(user_input, retrieved, CLINICAL_SYSTEM_PROMPT)
    
    # 3. Check for web search
    if result['source_type'] == 'Web':
        # Perform web search
        web_results = search_web_tool(user_input)
        
        # Re-generate with web results
        # We append web results to context
        web_context = "\n".join([f"Web Source: {r['title']} - {r['snippet']}" for r in web_results])
        
        # Simple re-prompting logic
        prompt = f"User asked: {user_input}. KB provided no results. Web search found:\n{web_context}\n\nAnswer the user based on these web results. Disclaimer: educational only."
        new_answer = grok_generate(prompt)
        
        result['answer_text'] = new_answer
        result['sources'] = web_results # Adjust structure if needed
        result['source_type'] = 'Web'
        
    state['agent_response'] = result
    return state

# Build Graph
workflow = StateGraph(AgentState)
workflow.add_node("receptionist", receptionist_node)
workflow.add_node("clinical", clinical_node)

workflow.set_entry_point("receptionist")

def route_receptionist(state: AgentState):
    if state.get('next_step') == 'clinical':
        return "clinical"
    return END

workflow.add_conditional_edges("receptionist", route_receptionist)
workflow.add_edge("clinical", END)

app_graph = workflow.compile()

def run_receptionist_flow(session_id: str, message: str, patient_record: Optional[Dict] = None, history: List = []) -> Dict:
    initial_state = {
        "session_id": session_id,
        "messages": history,
        "user_input": message,
        "patient_record": patient_record,
        "patient_id": patient_record['patient_id'] if patient_record else None,
        "next_step": None,
        "agent_response": None
    }
    
    # We want to start at receptionist
    # Since we compiled the graph, we can invoke it.
    # However, the graph is stateless between runs unless we persist.
    # Here we pass the full state in.
    
    final_state = app_graph.invoke(initial_state)
    return final_state['agent_response']

def run_clinical_flow(session_id: str, message: str, patient_id: str, history: List = []) -> Dict:
    # Fetch patient if not provided
    from backend.patient_db import get_patient_by_id
    patient_record = get_patient_by_id(patient_id)
    
    initial_state = {
        "session_id": session_id,
        "messages": history,
        "user_input": message,
        "patient_record": patient_record,
        "patient_id": patient_id,
        "next_step": None,
        "agent_response": None
    }
    
    # We want to force run clinical. 
    # But our graph starts at receptionist.
    # We can create a subgraph or just call the node function directly for this specific endpoint requirement.
    # The prompt says "POST /agent/clinical ... Runs RAG retrieval ...".
    # So we can just call clinical_node directly or a specific graph that starts there.
    
    # Let's just call the node logic directly to ensure we meet the endpoint requirement strictly.
    final_state = clinical_node(initial_state)
    return final_state['agent_response']
