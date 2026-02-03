import streamlit as st
import os
import shutil
import sys
import json
import re
import time
import datetime
import uuid
import plotly.graph_objects as go
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import backend
import chat_manager

try:
    import pandas as pd
except ImportError:
    pd = None

# Constants
TEMP_PDF_DIR = "temp_pdf"
CHROMA_DATA_ROOT = "chroma_data"
ACTIVE_DB_FILE = "active_db.txt"

@st.cache_resource
def get_embeddings():
    return backend.get_valid_embeddings()

def render_chart(chart_data):
    if not chart_data:
        return

    try:
        chart_type = chart_data.get("type")
        title = chart_data.get("title")
        x_label = chart_data.get("x_label")
        y_label = chart_data.get("y_label")
        data = chart_data.get("data", [])

        # Ensure labels are strings to force categorical axis
        labels = [str(item["label"]) for item in data]
        values = [item["value"] for item in data]

        fig = go.Figure()

        if chart_type == "bar":
            fig.add_trace(go.Bar(x=labels, y=values))
            fig.update_layout(xaxis=dict(type='category'), xaxis_title=x_label, yaxis_title=y_label)
        elif chart_type == "line":
            fig.add_trace(go.Scatter(x=labels, y=values, mode='lines+markers'))
            fig.update_layout(xaxis=dict(type='category'), xaxis_title=x_label, yaxis_title=y_label)
        elif chart_type == "pie":
            fig.add_trace(go.Pie(labels=labels, values=values))

        fig.update_layout(title=title)

        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error rendering chart: {e}")

@st.dialog("Källor")
def show_sources(sources):
    for source in sources:
        st.markdown(source)
        st.divider()

def get_active_db_path():
    if os.path.exists(ACTIVE_DB_FILE):
        with open(ACTIVE_DB_FILE, "r") as f:
            path = f.read().strip()
            if os.path.exists(path):
                return path
    return None

def set_active_db_path(path):
    with open(ACTIVE_DB_FILE, "w") as f:
        f.write(path)

def cleanup_old_sessions():
    """
    Attempts to clean up old database directories.
    Catches PermissionError to ignore locked folders (active sessions).
    """
    if not os.path.exists(CHROMA_DATA_ROOT):
        return

    active_path = get_active_db_path()

    # Get all DB paths referenced in chat history
    history = chat_manager.load_chat_history()
    saved_db_paths = set()
    for session in history.values():
        if "db_path" in session:
            saved_db_paths.add(os.path.abspath(session["db_path"]))

    for item in os.listdir(CHROMA_DATA_ROOT):
        item_path = os.path.join(CHROMA_DATA_ROOT, item)
        if os.path.isdir(item_path):
            abs_item_path = os.path.abspath(item_path)

            # Skip if it is the currently active one
            if active_path and abs_item_path == os.path.abspath(active_path):
                continue

            # Skip if it is referenced in a saved chat
            if abs_item_path in saved_db_paths:
                continue

            try:
                shutil.rmtree(item_path)
                # print(f"Cleaned up old session: {item}")
            except PermissionError:
                # Expected for locked/zombie folders on Windows
                pass
            except Exception as e:
                print(f"Error cleaning up {item}: {e}")

def clear_current_session():
    """
    Clears the current session state and attempts to delete the active database.
    """
    active_path = get_active_db_path()
    if active_path and os.path.exists(active_path):
        try:
            # We can only delete it if we release the handle.
            # In Streamlit, this is tricky because the vector store might still be in memory.
            # We'll rely on the 'cleanup_old_sessions' on next restart for full deletion,
            # but we can at least clear the pointer file and session state.
            if os.path.exists(ACTIVE_DB_FILE):
                os.remove(ACTIVE_DB_FILE)

            # Clear session state keys
            for key in ["vector_store", "chain", "messages", "initial_charts", "current_session_id"]:
                if key in st.session_state:
                    del st.session_state[key]

            st.success("Session cleared! Reloading...")
            time.sleep(1)
            st.rerun()

        except Exception as e:
            st.error(f"Error clearing session: {e}")

def load_session(session_id):
    """Loads a specific chat session."""
    session_data = chat_manager.get_chat_session(session_id)
    if not session_data:
        st.error("Session not found.")
        return

    db_path = session_data.get("db_path")
    if not db_path or not os.path.exists(db_path):
        st.error("Database for this session no longer exists.")
        return

    try:
        embeddings = get_embeddings()
        vector_store = backend.load_vector_store(db_path, embeddings)
        if vector_store:
            st.session_state.vector_store = vector_store
            st.session_state.chain = backend.get_conversational_chain(vector_store)
            st.session_state.messages = session_data.get("messages", [])
            st.session_state.initial_charts = session_data.get("initial_charts", [])
            st.session_state.current_session_id = session_id
            set_active_db_path(db_path)
            st.toast(f"Loaded chat: {session_data.get('title')}", icon="📂")
    except Exception as e:
        st.error(f"Failed to load session: {e}")

def main():
    st.set_page_config(page_title="Finans-AI", page_icon="💰", layout="wide")
    st.title("💰 Finans-AI: Financial Report Analyzer")

    # Initialize session state for messages if not present
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Initialize session state for initial summary charts
    if "initial_charts" not in st.session_state:
        st.session_state.initial_charts = []

    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None

    # Check for existing database on startup (only if no session is active)
    if "vector_store" not in st.session_state:
        active_db_path = get_active_db_path()
        if active_db_path:
            try:
                embeddings = get_embeddings()
                vector_store = backend.load_vector_store(active_db_path, embeddings)
                if vector_store:
                    st.session_state.vector_store = vector_store
                    st.session_state.chain = backend.get_conversational_chain(vector_store)
                    st.toast("Loaded existing database from disk.", icon="💾")
            except Exception as e:
                st.error(f"Failed to load existing database: {e}")

    # Lazy cleanup on startup
    if "cleanup_done" not in st.session_state:
        cleanup_old_sessions()
        st.session_state.cleanup_done = True

    # Sidebar
    with st.sidebar:
        st.header("Inställningar")

        # Layout Toggle
        layout_mode = st.radio(
            "Layout / Visningsläge",
            ["Desktop (Split View)", "Mobile (Tabs)"],
            index=0
        )

        st.divider()
        st.header("Sparade Chattar")

        # Saved Chats List
        history = chat_manager.load_chat_history()
        # Sort by date descending
        sorted_sessions = sorted(history.items(), key=lambda x: x[1].get("created_at", ""), reverse=True)

        session_options = {sid: data["title"] for sid, data in sorted_sessions}

        # Determine correct index for selectbox
        options_list = ["new_session"] + list(session_options.keys())
        default_index = 0

        if st.session_state.current_session_id in session_options:
            try:
                # +1 because "new_session" is at index 0
                default_index = list(session_options.keys()).index(st.session_state.current_session_id) + 1
            except ValueError:
                default_index = 0

        # Add "New Chat" option
        selected_session_id = st.selectbox(
            "Välj chatt",
            options=options_list,
            index=default_index,
            format_func=lambda x: "➕ Ny Analys" if x == "new_session" else session_options.get(x, "Okänd")
        )

        # Handle Session Switching
        if selected_session_id != "new_session":
            if st.session_state.current_session_id != selected_session_id:
                load_session(selected_session_id)
                st.rerun()
        elif selected_session_id == "new_session" and st.session_state.current_session_id is not None:
             # User selected "New Analys" but we are currently in a session.
             # We should essentially "clear" the view to allow upload, but not delete data.
             # Just clearing the state keys related to the current session view.
             for key in ["vector_store", "chain", "messages", "initial_charts", "current_session_id"]:
                if key in st.session_state:
                    del st.session_state[key]
             st.rerun()

        if st.session_state.current_session_id:
             if st.button("🗑️ Ta bort denna chatt"):
                 chat_manager.delete_chat_session(st.session_state.current_session_id)
                 clear_current_session() # Effectively resets view

        st.divider()
        st.header("Upload Reports")

        # Session Name Input (Only relevant for new sessions)
        session_name = st.text_input("Namn på analys (valfritt)", placeholder="T.ex. Apple Q3 2024")

        uploaded_files = st.file_uploader("Upload PDF files", type="pdf", accept_multiple_files=True)

        process_button = st.button("Process Documents")

        st.divider()
        with st.expander("🛠️ Debug & Tools"):
            if st.button("🗑️ Rensa databas", type="primary"):
                clear_current_session()

    # Processing Logic
    if process_button and uploaded_files:
        # 1. Clear/Create temp directory
        if os.path.exists(TEMP_PDF_DIR):
            shutil.rmtree(TEMP_PDF_DIR)
        os.makedirs(TEMP_PDF_DIR)

        # Create a UNIQUE directory for this run to avoid file locks on Windows
        if not os.path.exists(CHROMA_DATA_ROOT):
            os.makedirs(CHROMA_DATA_ROOT)

        new_db_path = os.path.join(CHROMA_DATA_ROOT, f"session_{uuid.uuid4()}")

        # 2. Save files
        with st.spinner("Saving uploaded files..."):
            for uploaded_file in uploaded_files:
                file_path = os.path.join(TEMP_PDF_DIR, uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

        # 3. Process
        with st.spinner("Processing documents..."):
            try:
                # Check for API Key
                if not os.getenv("GOOGLE_API_KEY"):
                    st.error("GOOGLE_API_KEY is missing. Please set it in the .env file.")
                else:
                    documents = backend.load_pdfs(TEMP_PDF_DIR)
                    if not documents:
                        st.warning("No text could be extracted from the PDFs.")
                    else:
                        chunks = backend.split_text(documents)
                        embeddings = get_embeddings()
                        vector_store = backend.create_vector_store(chunks, embeddings=embeddings, persist_directory=new_db_path)
                        chain = backend.get_conversational_chain(vector_store)

                        # Update active pointer
                        set_active_db_path(new_db_path)

                        # Store chain and vector_store in session state
                        st.session_state.chain = chain
                        st.session_state.vector_store = vector_store
                        st.session_state.messages = []

                        # Generate Summary Charts
                        st.toast("Generating summary charts...", icon="📊")
                        initial_charts = backend.generate_summary_charts(chain)
                        st.session_state.initial_charts = initial_charts

                        # Create Persistent Session
                        if not session_name:
                            session_name = uploaded_files[0].name

                        new_session_id = chat_manager.create_chat_session(session_name, new_db_path)
                        st.session_state.current_session_id = new_session_id

                        # Save initial state
                        chat_manager.update_chat_session(
                            new_session_id,
                            messages=[],
                            initial_charts=initial_charts
                        )

                        st.success("Documents processed successfully! You can now ask questions.")
                        time.sleep(1) # Brief pause so user sees success message
                        st.rerun() # Rerun to update sidebar list
            except Exception as e:
                st.error(f"An error occurred during processing: {e}")

    # Debug Interface
    if "vector_store" in st.session_state:
        with st.sidebar.expander("🔍 Debug: Utforska Databas"):
            active_path = get_active_db_path()
            if active_path:
                st.caption(f"📍 Database Location:")
                st.code(os.path.abspath(active_path))

            if st.button("Ladda & Visa Data"):
                try:
                    stored_docs = backend.get_all_documents(st.session_state.vector_store)
                    st.write(f"📊 Totalt antal text-chunks: **{len(stored_docs)}**")

                    if stored_docs:
                        # Create a cleaner list for display
                        data_for_display = []
                        for doc in stored_docs:
                            meta = doc.get("metadata", {})
                            data_for_display.append({
                                "ID": doc.get("id"),
                                "Filnamn": meta.get("source", "N/A"),
                                "Sida": meta.get("page", -1) + 1,
                                "Innehåll (förhandsvisning)": doc.get("content", "")[:100] + "..."
                            })

                        if pd:
                            df = pd.DataFrame(data_for_display)
                            try:
                                st.dataframe(df, width=None, use_container_width=True)
                            except:
                                st.dataframe(df)
                        else:
                             st.table(data_for_display[:10])
                             if len(data_for_display) > 10:
                                 st.info("Showing first 10 rows (install pandas for full table view)")
                except Exception as e:
                    st.error(f"Kunde inte hämta data: {e}")

    # Layout Rendering

    # Define containers based on layout mode
    if "Desktop" in layout_mode:
        col_charts, col_chat = st.columns([1, 1])
        chart_container = col_charts
        chat_container = col_chat
    else:
        tab_charts, tab_chat = st.tabs(["📊 Charts", "💬 Chat"])
        chart_container = tab_charts
        chat_container = tab_chat

    # Render Charts in Chart Container
    with chart_container:
        st.subheader("Finansiell Översikt")
        if "initial_charts" in st.session_state and st.session_state.initial_charts:
            for chart in st.session_state.initial_charts:
                render_chart(chart)
        elif "chain" in st.session_state:
             st.info("No automatic charts could be generated from the provided documents. Try asking for specific data in the chat.")
        else:
             st.info("Upload documents to generate summary charts.")

    # Render Chat in Chat Container
    with chat_container:
        st.subheader("Chat")
        # Display chat messages
        for i, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if "chart_data" in message:
                    data = message["chart_data"]
                    if isinstance(data, list):
                        for chart in data:
                            render_chart(chart)
                    else:
                        render_chart(data)
                if "sources" in message:
                    if st.button("Visa källor", key=f"sources_btn_{i}"):
                        show_sources(message["sources"])

    # Chat Input (Always at bottom, acts globally but we append to chat_container visual flow)
    if prompt := st.chat_input("Ask a question about the financial reports"):
        # Display user message
        st.session_state.messages.append({"role": "user", "content": prompt})

        # We manually render the user message in the chat container so it appears immediately
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate response
            if "chain" in st.session_state:
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        try:
                            response = st.session_state.chain.invoke({"input": prompt})
                            answer = response['answer']

                            # Extract JSON
                            chart_data_list = []
                            # Find all JSON blocks
                            json_matches = re.finditer(r'```json\s*(\{.*?\})\s*```', answer, re.DOTALL)

                            for match in json_matches:
                                json_str = match.group(1)
                                try:
                                    data = json.loads(json_str)
                                    chart_data_list.append(data)
                                    # Remove the JSON block from the answer
                                    answer = answer.replace(match.group(0), "")
                                except json.JSONDecodeError:
                                    pass

                            answer = answer.strip()
                            st.markdown(answer)

                            for chart in chart_data_list:
                                render_chart(chart)

                            # Process sources
                            sources_text = []
                            if "context" in response:
                                # Sort documents by page number
                                sorted_docs = sorted(response["context"], key=lambda x: x.metadata.get('page', 0))

                                for doc in sorted_docs:
                                    page = doc.metadata.get('page', -1) + 1
                                    source_info = f"**Sida {page}:**\n{doc.page_content}"
                                    sources_text.append(source_info)

                            # Append message to state
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": answer,
                                "sources": sources_text,
                                "chart_data": chart_data_list
                            })

                            # Save Chat History if session is active
                            if st.session_state.current_session_id:
                                chat_manager.update_chat_session(
                                    st.session_state.current_session_id,
                                    messages=st.session_state.messages
                                )

                            # Show button for the new message
                            if sources_text:
                                if st.button("Visa källor", key=f"sources_btn_{len(st.session_state.messages)-1}"):
                                    show_sources(sources_text)

                        except Exception as e:
                            st.error(f"Error generating response: {e}")
            else:
                 with st.chat_message("assistant"):
                    st.warning("Please upload and process documents first.")

if __name__ == "__main__":
    main()
