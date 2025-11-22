# Architecture Notes: Post-Discharge Medical AI Assistant

## 1. System Overview

The Post-Discharge Medical AI Assistant is a modular, multi-agent system designed to assist patients with post-discharge care queries. It leverages a Retrieval-Augmented Generation (RAG) pipeline to ground answers in a specific clinical knowledge base (Nephrology PDF) and uses a Receptionist/Clinical agent pattern to handle triage and specific medical inquiries.

## 2. Core Components

### A. Frontend (Streamlit)
- **Role**: User interface for patients.
- **Features**:
  - Chat interface for natural language interaction.
  - Sidebar for patient identification and record visualization.
  - Visual badges (`KB`, `Web`, `System`) to indicate the source of information.
  - Real-time log viewer for observability.
- **Communication**: Interacts with the Backend via REST API calls.

### B. Backend (FastAPI)
- **Role**: Central API server handling requests, session management, and agent orchestration.
- **Endpoints**:
  - `/session/start`: Initializes user sessions.
  - `/patient`: Handles patient lookup.
  - `/agent/receptionist`: Entry point for the Receptionist Agent.
  - `/agent/clinical`: Entry point for the Clinical Agent.
  - `/logs`: Exposes system logs.

### C. Multi-Agent Orchestration (LangGraph)
- **Receptionist Agent**:
  - **Responsibility**: Identity verification, record retrieval, summary, and initial triage.
  - **Logic**: Uses heuristics and LLM calls to determine if the user is stating their name or asking a question. Checks for urgent keywords (e.g., "chest pain") to flag emergencies.
- **Clinical Agent**:
  - **Responsibility**: Answering medical questions based on the KB.
  - **Logic**: Receives patient context and query. Executes the RAG pipeline. Decides if Web Search is needed if KB retrieval is insufficient.

### D. RAG Pipeline
- **Ingestion**:
  - **Source**: `comprehensive-clinical-nephrology.pdf`.
  - **Process**: Text extraction -> Chunking (~800 tokens) -> Embedding (`all-mpnet-base-v2`) -> Storage (ChromaDB).
- **Retrieval**:
  - **Query**: User question + Patient Diagnosis (context injection).
  - **Mechanism**: Semantic search in ChromaDB to find top-k relevant chunks.
- **Generation**:
  - **Model**: Grok LLM (via wrapper).
  - **Prompting**: System prompt enforces strict adherence to provided chunks and citation format.

### E. Data Storage
- **Vector Database**: ChromaDB (Local persistent) for storing KB embeddings.
- **Relational Database**: SQLite for storing patient records (`patients` table).
- **File System**: Logs stored in `logs/app.log`.

## 3. Data Flow

1. **User Login/Greeting**:
   - User sends "Hi, I'm John".
   - **Receptionist Agent** parses name, queries **SQLite**, retrieves record.
   - Returns summary + triage question.

2. **Clinical Query**:
   - User asks "Why are my legs swelling?".
   - **Receptionist** routes to **Clinical Agent** (or Frontend calls Clinical endpoint directly if context exists).
   - **Clinical Agent** calls `retrieve()` from **ChromaDB**.
   - Retrieved chunks + Query sent to **Grok**.
   - **Grok** generates answer with citations.
   - Response returned to UI with `source_type: KB`.

3. **Web Fallback**:
   - If Grok determines KB is insufficient (returns "web_search_needed"), the **Clinical Agent** calls the Web Search Tool (stub).
   - New answer generated using Web results.
   - Response returned with `source_type: Web`.

## 4. Security & Safety

- **Medical Disclaimer**: Hardcoded in UI and appended to every clinical response.
- **Urgent Triage**: Receptionist agent explicitly checks for emergency keywords and advises immediate care.
- **Data Privacy**: Patient data stored locally in SQLite. No external transmission of PII (in this POC).

## 5. Future Improvements

- **Real Web Search**: Replace stub with Google Search API or Tavily.
- **Authentication**: Implement secure user auth instead of simple name lookup.
- **Tokenizer**: Use a real tokenizer (e.g., tiktoken) for precise chunking.
- **Evaluation**: Add Ragas or TruLens for RAG pipeline evaluation.
