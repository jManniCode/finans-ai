import os
import shutil
import uuid
import json
import re
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Import local modules
# We are inside backend/ directory, but running as a module 'backend.main' usually
# Relative imports work if run as 'python -m backend.main' or if 'backend' is a package.
# From inside backend/main.py, '.' refers to backend package.
from . import backend
from . import chat_manager

load_dotenv()

app = FastAPI(title="Finans-AI Backend")

# CORS configuration
origins = [
    "http://localhost:5173", # Vite default
    "http://localhost:3000",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
TEMP_PDF_ROOT = "temp_pdf"
CHROMA_DATA_ROOT = "chroma_data"

# Global cache for the active chain/vector_store to avoid reloading on every request
# In a multi-user production app, this would need a better design (e.g., LRU cache).
class SessionCache:
    def __init__(self):
        self.session_id: Optional[str] = None
        self.chain: Any = None
        self.vector_store: Any = None

    def clear(self):
        self.session_id = None
        self.chain = None
        self.vector_store = None

session_cache = SessionCache()

# Pydantic Models
class ChatRequest(BaseModel):
    prompt: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[str]
    charts: List[Dict[str, Any]]

class SessionInfo(BaseModel):
    id: str
    title: str
    created_at: str

@app.get("/")
def read_root():
    return {"message": "Finans-AI Backend is running"}

@app.get("/api/sessions", response_model=List[SessionInfo])
def get_sessions():
    history = chat_manager.load_chat_history()
    sessions = []
    for sid, data in history.items():
        sessions.append(SessionInfo(
            id=sid,
            title=data.get("title", "Untitled"),
            created_at=data.get("created_at", "")
        ))
    # Sort by created_at desc
    sessions.sort(key=lambda x: x.created_at, reverse=True)
    return sessions

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    session_data = chat_manager.get_chat_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_data

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    chat_manager.delete_chat_session(session_id)
    if session_cache.session_id == session_id:
        session_cache.clear()
    return {"message": "Session deleted"}

@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # 1. Create unique temp directory for this upload
    if not os.path.exists(TEMP_PDF_ROOT):
        os.makedirs(TEMP_PDF_ROOT)

    upload_id = str(uuid.uuid4())
    current_temp_dir = os.path.join(TEMP_PDF_ROOT, upload_id)
    os.makedirs(current_temp_dir)

    try:
        # 2. Save files
        saved_files = []
        for file in files:
            file_path = os.path.join(current_temp_dir, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_files.append(file.filename)

        # 3. Process
        # Create a unique DB path
        if not os.path.exists(CHROMA_DATA_ROOT):
            os.makedirs(CHROMA_DATA_ROOT)

        new_db_path = os.path.join(CHROMA_DATA_ROOT, f"session_{uuid.uuid4()}")

        # Load and Split
        documents = backend.load_pdfs(current_temp_dir)
        if not documents:
            raise HTTPException(status_code=400, detail="No text extracted from PDFs")

        chunks = backend.split_text(documents)

        # Create Vector Store
        # Check API KEY
        if not os.getenv("GOOGLE_API_KEY"):
            raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not set")

        embeddings = backend.get_valid_embeddings()
        vector_store = backend.create_vector_store(chunks, embeddings=embeddings, persist_directory=new_db_path)
        chain = backend.get_conversational_chain(vector_store)

        # Generate Summary Charts
        initial_charts = backend.generate_summary_charts(chain)

        # Create Session
        session_name = saved_files[0] if saved_files else "New Analysis"
        session_id = chat_manager.create_chat_session(session_name, new_db_path)
        chat_manager.update_chat_session(session_id, initial_charts=initial_charts)

        # Update Cache
        session_cache.session_id = session_id
        session_cache.vector_store = vector_store
        session_cache.chain = chain

        return {
            "session_id": session_id,
            "initial_charts": initial_charts,
            "message": "Files processed successfully"
        }

    except Exception as e:
        # print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temp dir
        if os.path.exists(current_temp_dir):
            shutil.rmtree(current_temp_dir)

@app.post("/api/chat/{session_id}", response_model=ChatResponse)
def chat(session_id: str, request: ChatRequest):
    prompt = request.prompt

    # Check cache first
    if session_cache.session_id == session_id and session_cache.chain:
        chain = session_cache.chain
    else:
        # Load session
        session_data = chat_manager.get_chat_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")

        db_path = session_data.get("db_path")
        if not db_path or not os.path.exists(db_path):
             raise HTTPException(status_code=404, detail="Database not found for this session")

        embeddings = backend.get_valid_embeddings()
        vector_store = backend.load_vector_store(db_path, embeddings)
        chain = backend.get_conversational_chain(vector_store)

        # Update cache
        session_cache.session_id = session_id
        session_cache.vector_store = vector_store
        session_cache.chain = chain

    # Invoke chain
    try:
        response = chain.invoke({"input": prompt})
        answer = response['answer']

        # Extract Charts
        chart_data_list = []
        json_matches = re.finditer(r'```json\s*(\{.*?\})\s*```', answer, re.DOTALL)
        for match in json_matches:
            json_str = match.group(1)
            try:
                data = json.loads(json_str)
                chart_data_list.append(data)
                # Remove JSON from text
                answer = answer.replace(match.group(0), "")
            except json.JSONDecodeError:
                pass

        answer = answer.strip()

        # Extract Sources
        sources_text = []
        if "context" in response:
            sorted_docs = sorted(response["context"], key=lambda x: x.metadata.get('page', 0))
            for doc in sorted_docs:
                page = doc.metadata.get('page', -1) + 1
                source_info = f"**Sida {page}:**\n{doc.page_content}"
                sources_text.append(source_info)

        # Save to history
        session_data = chat_manager.get_chat_session(session_id)
        messages = session_data.get("messages", [])
        messages.append({"role": "user", "content": prompt})
        messages.append({
            "role": "assistant",
            "content": answer,
            "sources": sources_text,
            "chart_data": chart_data_list
        })
        chat_manager.update_chat_session(session_id, messages=messages)

        return ChatResponse(
            answer=answer,
            sources=sources_text,
            charts=chart_data_list
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
