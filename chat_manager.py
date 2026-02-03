import os
import json
import uuid
import datetime

CHAT_HISTORY_FILE = "chat_history.json"

def load_chat_history():
    """Loads the chat history metadata from a JSON file."""
    if not os.path.exists(CHAT_HISTORY_FILE):
        return {}
    try:
        with open(CHAT_HISTORY_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_chat_history(history):
    """Saves the chat history metadata to a JSON file."""
    with open(CHAT_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

def create_chat_session(title, db_path):
    """Creates a new chat session entry."""
    session_id = str(uuid.uuid4())
    history = load_chat_history()
    history[session_id] = {
        "title": title,
        "db_path": db_path,
        "created_at": datetime.datetime.now().isoformat(),
        "messages": [],
        "initial_charts": []
    }
    save_chat_history(history)
    return session_id

def update_chat_session(session_id, messages=None, initial_charts=None):
    """Updates an existing chat session with new messages or charts."""
    history = load_chat_history()
    if session_id in history:
        if messages is not None:
            history[session_id]["messages"] = messages
        if initial_charts is not None:
            history[session_id]["initial_charts"] = initial_charts
        save_chat_history(history)

def get_chat_session(session_id):
    """Retrieves a specific chat session."""
    history = load_chat_history()
    return history.get(session_id)

def delete_chat_session(session_id):
    """Deletes a chat session from history."""
    history = load_chat_history()
    if session_id in history:
        del history[session_id]
        save_chat_history(history)
