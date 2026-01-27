import streamlit as st
import os
import shutil
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import backend, handling missing dependencies gracefully
try:
    import backend
except ImportError as e:
    # Check specifically for langchain_community or other likely missing packages
    if "langchain_community" in str(e):
        st.error("Missing dependency: `langchain-community`.")
        st.error("Please run: `pip install -r requirements.txt` to install all required packages.")
        st.stop()
    else:
        # Re-raise other ImportErrors to avoid hiding legitimate bugs
        raise e

# Constants
TEMP_PDF_DIR = "temp_pdf"

def main():
    st.set_page_config(page_title="Finans-AI", page_icon="💰")
    st.title("💰 Finans-AI: Financial Report Analyzer")

    # Initialize session state for messages if not present
    if "messages" not in st.session_state:
        st.session_state.messages = []

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
                        vector_store = backend.create_vector_store(chunks)
                        chain = backend.get_conversational_chain(vector_store)

                        # Store chain in session state
                        st.session_state.chain = chain
                        # Clear chat history to start fresh
                        st.session_state.messages = []
                        st.success("Documents processed successfully! You can now ask questions.")
            except Exception as e:
                st.error(f"An error occurred during processing: {e}")

    # Chat Interface
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "sources" in message:
                with st.expander("Visa källor"):
                    for source in message["sources"]:
                        st.markdown(source)

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
                        st.markdown(answer)

                        # Process sources
                        sources_text = []
                        if "context" in response:
                            # Limit to top 5 sources to reduce clutter
                            for doc in response["context"][:5]:
                                # Add 1 to page number for user-friendly display (assuming 0-indexed)
                                page = doc.metadata.get('page', -1) + 1
                                # Show full content to allow verifying numbers
                                source_info = f"**Sida {page}:**\n{doc.page_content}"
                                sources_text.append(source_info)

                        if sources_text:
                            with st.expander("Visa källor"):
                                for source in sources_text:
                                    st.markdown(source)

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": answer,
                            "sources": sources_text
                        })
                    except Exception as e:
                        st.error(f"Error generating response: {e}")
        else:
            with st.chat_message("assistant"):
                st.warning("Please upload and process documents first.")

if __name__ == "__main__":
    main()
