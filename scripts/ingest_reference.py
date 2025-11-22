import os
import uuid
import logging
from pypdf import PdfReader
from backend.rag import chunk_text, upsert_chunks_to_chroma

# Configuration
# The path where the user has the file locally
LOCAL_PDF_PATH = r"C:\Users\shrishti\Desktop\clinical_nephrology_rag\post_discharge_ai_poc\comprehensive-clinical-nephrology.pdf"
# The path to use in metadata as per requirements
METADATA_SOURCE_PATH = "/mnt/data/GenAI_Intern_Assignment.pdf"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ingest_pdf(file_path: str):
    if not os.path.exists(file_path):
        logger.error(f"File not found at {file_path}. Please ensure the PDF is at this location.")
        return

    logger.info(f"Reading PDF from {file_path}...")
    try:
        reader = PdfReader(file_path)
    except Exception as e:
        logger.error(f"Failed to read PDF: {e}")
        return

    all_chunks = []
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if not text:
            continue
            
        # Chunk the text
        chunks = chunk_text(text)
        
        for chunk in chunks:
            chunk_record = {
                "text": chunk,
                "source": METADATA_SOURCE_PATH,
                "page": i + 1, # 1-based page number
                "chunk_id": str(uuid.uuid4())
            }
            all_chunks.append(chunk_record)
            
    logger.info(f"Extracted {len(all_chunks)} chunks. Upserting to ChromaDB...")
    upsert_chunks_to_chroma(all_chunks)
    logger.info("Ingestion complete.")

if __name__ == "__main__":
    # Check if user provided a path arg, else use default
    import sys
    path = LOCAL_PDF_PATH
    if len(sys.argv) > 1:
        path = sys.argv[1]
        
    ingest_pdf(path)
