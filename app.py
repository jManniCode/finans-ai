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

        st.plotly_chart(fig)
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

@st.dialog("Ta bort analys?")
def confirm_delete_session(session_id):
    st.write("Är du säker på att du vill ta bort denna analys? Detta går inte att ångra.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Avbryt", width="stretch"):
            st.rerun()
    with col2:
        if st.button("Ta bort", type="primary", width="stretch"):
            chat_manager.delete_chat_session(session_id)
            clear_current_session()

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
            # st.toast(f"Loaded chat: {session_data.get('title')}", icon="📂")
    except Exception as e:
        st.error(f"Failed to load session: {e}")

def render_new_analysis_view():
    """Renders the view for creating a new analysis (uploading files)."""
    st.header("Starta Ny Analys")
    st.markdown("Ladda upp dina finansiella rapporter (PDF) för att komma igång.")

    with st.container():
        col1, col2 = st.columns([2, 1])
        with col1:
            session_name = st.text_input("Namn på analys (valfritt)")
            uploaded_files = st.file_uploader("Ladda upp PDF-filer", type="pdf", accept_multiple_files=True)
            process_button = st.button("Processera & Analysera", type="primary")

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

                        st.success("Documents processed successfully!")
                        time.sleep(1)
                        st.rerun()
            except Exception as e:
                st.error(f"An error occurred during processing: {e}")

def render_active_session_view(layout_mode):
    """Renders the active chat and chart view."""

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
            # Create a selection of charts
            chart_titles = [c.get("title", f"Chart {i+1}") for i, c in enumerate(st.session_state.initial_charts)]

            # Use columns as buttons for "knappval" feel
            cols = st.columns(len(chart_titles))

            # State to track active chart
            if "active_chart_index" not in st.session_state:
                st.session_state.active_chart_index = None

            # Render buttons
            for i, title in enumerate(chart_titles):
                with cols[i]:
                    if st.button(title, key=f"chart_btn_{i}", use_container_width=True):
                        st.session_state.active_chart_index = i

            # Render selected chart
            if st.session_state.active_chart_index is not None:
                st.markdown("---")
                render_chart(st.session_state.initial_charts[st.session_state.active_chart_index])

                # Close button
                if st.button("Dölj graf", key="close_chart"):
                    st.session_state.active_chart_index = None
                    st.rerun()
            else:
                 st.caption("Välj en kategori ovan för att visualisera data.")

        elif "chain" in st.session_state:
             st.info("No automatic charts could be generated from the provided documents. Try asking for specific data in the chat.")
        else:
             st.info("Upload documents to generate summary charts.")

    # Render Chat in Chat Container
    with chat_container:
        st.subheader("Chat")

        # Empty State Guidance
        if not st.session_state.messages:
            st.markdown("#### 👋 Välkommen!")
            st.markdown("Jag har analyserat dina dokument och är redo att svara på frågor.")
            st.caption("Använd snabbvalen nedan eller skriv din egen fråga för att komma igång.")

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

    # Quick Start Buttons (Persistent)
    selected_prompt = None

    # Render outside chat container to keep them near the input
    st.caption("Förslag på frågor:")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Sammanfatta", key="qs_summary", use_container_width=True):
            selected_prompt = "Sammanfatta de viktigaste finansiella punkterna i rapporten."
    with c2:
        if st.button("Risker", key="qs_risks", use_container_width=True):
            selected_prompt = "Vilka är de största riskerna som nämns?"
    with c3:
        if st.button("Vinsttrend", key="qs_profit", use_container_width=True):
            selected_prompt = "Hur ser vinstutvecklingen ut över tid?"

    # Chat Input
    chat_input_value = st.chat_input("Ask a question about the financial reports")
    prompt = chat_input_value or selected_prompt

    if prompt:
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

def main():
    st.set_page_config(page_title="Finans-AI", page_icon="💰", layout="wide")
    # st.title("💰 Finans-AI: Financial Report Analyzer") # Removed to make it cleaner, or keep? Keeping logo in sidebar is better.

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

        # NOTE: logic adjusted here: Only load active DB if we are NOT explicitly in "New Analysis" mode.
        # But "New Analysis" mode is state=None.
        # The problem is that rerun() re-reads this.
        # We need to rely on the fact that if we just clicked "New Analysis", we should probably CLEAR the active_db file.

        if active_db_path:
            try:
                embeddings = get_embeddings()
                vector_store = backend.load_vector_store(active_db_path, embeddings)
                if vector_store:
                    # Try to match the active DB with a session ID
                    history = chat_manager.load_chat_history()
                    found_session = False
                    for sid, data in history.items():
                        if data.get("db_path") and os.path.abspath(data["db_path"]) == os.path.abspath(active_db_path):
                            # Only restore if we actually found a valid session
                            st.session_state.vector_store = vector_store
                            st.session_state.chain = backend.get_conversational_chain(vector_store)
                            st.session_state.current_session_id = sid
                            st.session_state.messages = data.get("messages", [])
                            st.session_state.initial_charts = data.get("initial_charts", [])
                            found_session = True
                            break

                    if found_session:
                        st.toast("Restored active session.", icon="🔄")
                    else:
                         # If we have a vector store but no matching session ID (maybe deleted?), clear it.
                         pass

            except Exception as e:
                # st.error(f"Failed to load existing database: {e}")
                pass

    # Lazy cleanup on startup
    if "cleanup_done" not in st.session_state:
        cleanup_old_sessions()
        st.session_state.cleanup_done = True

    # Sidebar
    with st.sidebar:
        st.title("💰 Finans-AI")

        # New Chat Button
        if st.button("➕ Ny Analys", type="primary", width="stretch"):
             # Clear session state keys to reset view
             for key in ["vector_store", "chain", "messages", "initial_charts", "current_session_id"]:
                if key in st.session_state:
                    del st.session_state[key]

             # ALSO clear the active DB file so we don't reload it on rerun
             if os.path.exists(ACTIVE_DB_FILE):
                 os.remove(ACTIVE_DB_FILE)

             st.rerun()

        st.subheader("Historik")
        # Load history
        history = chat_manager.load_chat_history()
        sorted_sessions = sorted(history.items(), key=lambda x: x[1].get("created_at", ""), reverse=True)

        # Display list of sessions
        for sid, data in sorted_sessions:
            # Highlight current session? Streamlit buttons don't support "active" state easily visually
            # but we can disable the current one or just show it.
            button_label = data["title"]
            if sid == st.session_state.current_session_id:
                button_label = f"📂 {button_label}" # Indicate active

            if st.button(button_label, key=sid, width="stretch"):
                 if st.session_state.current_session_id != sid:
                     load_session(sid)
                     st.rerun()

        st.divider()
        st.header("Inställningar")

        # Layout Toggle
        layout_mode = st.radio(
            "Layout / Visningsläge",
            ["Desktop (Split View)", "Mobile (Tabs)"],
            index=0
        )

        if st.session_state.current_session_id:
             if st.button("🗑️ Ta bort denna chatt", width="stretch"):
                 confirm_delete_session(st.session_state.current_session_id)

        st.divider()
        with st.expander("🛠️ Debug & Tools"):
            if st.button("🗑️ Rensa databas", type="primary"):
                clear_current_session()

            # Debug Interface
            if "vector_store" in st.session_state:
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
                                    st.dataframe(df, width="stretch")
                                except:
                                    st.dataframe(df)
                            else:
                                 st.table(data_for_display[:10])
                                 if len(data_for_display) > 10:
                                     st.info("Showing first 10 rows (install pandas for full table view)")
                    except Exception as e:
                        st.error(f"Kunde inte hämta data: {e}")

    # Main Content Area Logic
    if st.session_state.current_session_id is None:
        render_new_analysis_view()
    else:
        render_active_session_view(layout_mode)

if __name__ == "__main__":
    main()
