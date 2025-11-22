import os
import uuid
import logging
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from backend.grok_wrapper import grok_generate
from backend.prompts import RAG_GENERATION_PROMPT_TEMPLATE, CLINICAL_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", "./chroma_db")
EMBEDDING_MODEL_NAME = "all-mpnet-base-v2"

# Initialize global instances
_chroma_client = None
_embedding_model = None
_collection = None

def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    return _chroma_client

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model

def get_collection():
    global _collection
    client = get_chroma_client()
    # Get or create collection
    _collection = client.get_or_create_collection(name="nephrology_kb")
    return _collection

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """
    Simple character/token approximation chunking. 
    For better results, a tokenizer should be used, but character/word split is often sufficient for POC.
    Here we assume 'tokens' roughly map to 4 chars.
    """
    # Using a simple sliding window of words for simplicity in this POC
    words = text.split()
    chunks = []
    
    # Approximate tokens -> words (1 token ~= 0.75 words, so 800 tokens ~= 600 words)
    # Let's stick to the prompt's "chunk_size approx 800 tokens".
    # We'll use 600 words as chunk size, 75 words as overlap.
    
    word_chunk_size = 600
    word_overlap = 75
    
    if len(words) <= word_chunk_size:
        return [text]
        
    start = 0
    while start < len(words):
        end = start + word_chunk_size
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        start += (word_chunk_size - word_overlap)
        
    return chunks

def embed_texts(texts: List[str]) -> List[List[float]]:
    model = get_embedding_model()
    embeddings = model.encode(texts)
    return embeddings.tolist()

def upsert_chunks_to_chroma(chunks: List[Dict[str, Any]]):
    """
    chunks: list of dicts with keys: text, source, page, chunk_id
    """
    collection = get_collection()
    
    texts = [c['text'] for c in chunks]
    metadatas = [{"source": c['source'], "page": c['page'], "chunk_id": c['chunk_id']} for c in chunks]
    ids = [c['chunk_id'] for c in chunks]
    
    embeddings = embed_texts(texts)
    
    collection.upsert(
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )
    logger.info(f"Upserted {len(chunks)} chunks to ChromaDB.")

def retrieve(query: str, k: int = 5) -> List[Dict[str, Any]]:
    collection = get_collection()
    model = get_embedding_model()
    query_embedding = model.encode([query]).tolist()
    
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=k
    )
    
    # Format results
    retrieved = []
    if results['documents']:
        for i in range(len(results['documents'][0])):
            item = {
                "text": results['documents'][0][i],
                "source": results['metadatas'][0][i]['source'],
                "page": results['metadatas'][0][i]['page'],
                "chunk_id": results['metadatas'][0][i]['chunk_id'],
                "score": results['distances'][0][i] if 'distances' in results else 0 
                # Note: Chroma returns distances by default (lower is better for L2, higher is better for Cosine if configured)
                # Default is L2. We might want to convert to similarity or just pass as is.
            }
            retrieved.append(item)
            
    return retrieved

def generate_answer(query: str, retrieved_chunks: List[Dict], system_prompt_template: str = CLINICAL_SYSTEM_PROMPT, use_grok: bool = True) -> Dict[str, Any]:
    
    # Format context
    context_text = ""
    for i, chunk in enumerate(retrieved_chunks):
        context_text += f"Chunk {i+1} (Page {chunk['page']}, ID {chunk['chunk_id']}):\n{chunk['text']}\n\n"
        
    full_prompt = RAG_GENERATION_PROMPT_TEMPLATE.format(
        system_prompt=system_prompt_template,
        context_chunks=context_text,
        user_query=query
    )
    
    if use_grok:
        answer_text = grok_generate(full_prompt)
    else:
        answer_text = "Grok generation disabled."

    # Check if web search is needed based on the answer
    # The prompt says: "If KB lacks answer... return 'web_search_needed'"
    # We rely on the LLM to output this string.
    
    source_type = "KB"
    if "web_search_needed" in answer_text.lower():
        source_type = "Web" # This will trigger the web search flow in the agent
        
    return {
        "answer_text": answer_text,
        "sources": retrieved_chunks,
        "source_type": source_type
    }
