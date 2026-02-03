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

def cleanup_old_sessions():
    """
    Attempts to clean up old database directories.
    Catches PermissionError to ignore locked folders (active sessions).
    """
    if not os.path.exists(CHROMA_DATA_ROOT):
        return

    active_path = get_active_db_path()

    for item in os.listdir(CHROMA_DATA_ROOT):
        item_path = os.path.join(CHROMA_DATA_ROOT, item)
        if os.path.isdir(item_path):
            # Skip the currently active one if known
            if active_path and os.path.abspath(item_path) == os.path.abspath(active_path):
                continue

            try:
                shutil.rmtree(item_path)
                # print(f"Cleaned up old session: {item}")
            except PermissionError:
                # Expected for locked/zombie folders on Windows
                pass
            except Exception as e:
                print(f"Error cleaning up {item}: {e}")

def main():
    st.set_page_config(page_title="Finans-AI", page_icon="💰")
    st.title("💰 Finans-AI: Financial Report Analyzer")

    # Initialize session state for messages if not present
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Check for existing database on startup
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
        st.header("Upload Reports")
        uploaded_files = st.file_uploader("Upload PDF files", type="pdf", accept_multiple_files=True)

        process_button = st.button("Process Documents")

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
                        # Clear chat history to start fresh
                        st.session_state.messages = []
                        st.success("Documents processed successfully! You can now ask questions.")
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
                            st.dataframe(df, use_container_width=True)
                        else:
                             st.table(data_for_display[:10]) # Fallback if pandas missing
                             if len(data_for_display) > 10:
                                 st.info("Showing first 10 rows (install pandas for full table view)")
                except Exception as e:
                    st.error(f"Kunde inte hämta data: {e}")

    # Chat Interface
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "chart_data" in message:
                # Handle single chart or list of charts
                data = message["chart_data"]
                if isinstance(data, list):
                    for chart in data:
                        render_chart(chart)
                else:
                    render_chart(data)
            if "sources" in message:
                if st.button("Visa källor", key=f"sources_btn_{i}"):
                    show_sources(message["sources"])

    if prompt := st.chat_input("Ask a question about the financial reports"):
        # Display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
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
                            # Sort documents by page number for user-friendly display
                            sorted_docs = sorted(response["context"], key=lambda x: x.metadata.get('page', 0))

                            # Display all retrieved sources so the user can verify all citations
                            for doc in sorted_docs:
                                # Add 1 to page number for user-friendly display (assuming 0-indexed)
                                page = doc.metadata.get('page', -1) + 1
                                # Show full content to allow verifying numbers
                                source_info = f"**Sida {page}:**\n{doc.page_content}"
                                sources_text.append(source_info)

                        # Append message first so we have the index for the key
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": answer,
                            "sources": sources_text,
                            "chart_data": chart_data_list
                        })

                        # Show button for the new message
                        if sources_text:
                            # Use a unique key based on the length of messages (which is the index of this new message)
                            if st.button("Visa källor", key=f"sources_btn_{len(st.session_state.messages)-1}"):
                                show_sources(sources_text)

                    except Exception as e:
                        st.error(f"Error generating response: {e}")
        else:
            with st.chat_message("assistant"):
                st.warning("Please upload and process documents first.")

if __name__ == "__main__":
    main()
