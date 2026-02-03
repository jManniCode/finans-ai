import os
import json
import re
import time
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from google.api_core.exceptions import ResourceExhausted

# Load environment variables
load_dotenv()

def load_pdfs(directory):
    """
    Loads all PDF files from the specified directory.
    """
    documents = []
    if not os.path.exists(directory):
        print(f"Directory {directory} does not exist.")
        return documents

    for filename in os.listdir(directory):
        if filename.endswith('.pdf'):
            file_path = os.path.join(directory, filename)
            try:
                loader = PyPDFLoader(file_path)
                documents.extend(loader.load())
                print(f"Loaded {filename}")
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    return documents

def split_text(documents):
    """
    Splits the documents into chunks and embeds page numbers.
    """
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)

    # Embed page number into the content of each chunk
    for chunk in chunks:
        page_num = chunk.metadata.get('page', -1) + 1  # Assuming 0-indexed pages
        chunk.page_content = f"[Page {page_num}] {chunk.page_content}"
        # Ensure 'source' is in metadata, defaulting to 'unknown' if missing
        if 'source' not in chunk.metadata:
            chunk.metadata['source'] = 'unknown'
        # Clean up source path to just filename for cleaner display
        else:
             chunk.metadata['source'] = os.path.basename(chunk.metadata['source'])

    return chunks

# Global variable to cache the working model name
_valid_model_name = None

def get_valid_embeddings():
    """
    Attempts to find a working embedding model by testing available options.
    """
    global _valid_model_name

    # If we already found a valid model, use it directly to avoid redundant network checks
    if _valid_model_name:
        return GoogleGenerativeAIEmbeddings(model=_valid_model_name)

    candidate_models = ["models/text-embedding-004", "models/embedding-001"]

    for model_name in candidate_models:
        try:
            embeddings = GoogleGenerativeAIEmbeddings(model=model_name)
            # Test the embeddings
            embeddings.embed_query("test")
            print(f"Successfully selected embedding model: {model_name}")
            _valid_model_name = model_name
            return embeddings
        except Exception as e:
            print(f"Failed to initialize model {model_name}: {e}")
            continue

    # Fallback to default if everything fails (or let it crash with a clear error)
    print("Could not verify any specific model, falling back to 'models/embedding-001'")
    return GoogleGenerativeAIEmbeddings(model="models/embedding-001")

def create_vector_store(chunks, embeddings=None, persist_directory=None):
    """
    Creates a Chroma vector store from the document chunks.
    """
    if embeddings is None:
        embeddings = get_valid_embeddings()

    # Create vector store
    if persist_directory:
        vector_store = Chroma.from_documents(chunks, embeddings, persist_directory=persist_directory)
    else:
        vector_store = Chroma.from_documents(chunks, embeddings)

    return vector_store

def load_vector_store(persist_directory, embeddings=None):
    """
    Loads an existing Chroma vector store from the specified directory.
    """
    if embeddings is None:
        embeddings = get_valid_embeddings()

    if os.path.exists(persist_directory):
        vector_store = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        return vector_store
    else:
        print(f"Directory {persist_directory} does not exist.")
        return None

def get_conversational_chain(vector_store):
    """
    Creates a conversational chain using the vector store.
    """
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3)

    retriever = vector_store.as_retriever(search_kwargs={"k": 20})

    # Prompt template for financial summarization and Q&A
    system_prompt = (
        "You are an expert financial analyst assistant. "
        "Use the following pieces of retrieved context to answer the question. "
        "Answer in the same language as the user's question. "
        "If the user asks for a summary, provide a concise and factual financial summary based on the context. "
        "If the user asks about the sentiment, assess the overall tone (e.g., positive, negative, neutral, cautious) based on the context and explain your reasoning. "
        "When answering, you MUST cite the source page number for every fact you mention. "
        "The text chunks provided contain page numbers in the format '[Page X]'. Use these tags to ensure your citations are accurate. "
        "Format citations as [Page X]. Example: 'Revenue increased by 10% [Page 3]'. "
        "If the answer is not in the context, say that you don't know. "
        "Keep the answer concise."
        "\n\n"
        "If the answer includes financial figures suitable for a visualization (e.g., trends over years, or comparisons between periods like Q3 2024 vs Q3 2025, or distribution/proportions), "
        "or if the user explicitly asks for a graph, you MUST generate a JSON object representing this data at the very end of your response. "
        "Use 'bar' for comparisons, 'line' for trends, and 'pie' for proportions/distributions. "
        "Even for simple comparisons (e.g., This Year vs Last Year), generate a bar chart. "
        "The JSON must be enclosed in triple backticks with 'json' identifier, like this:\n"
        "```json\n"
        "{{\n"
        "    \"type\": \"bar\" or \"line\" or \"pie\",\n"
        "    \"title\": \"Chart Title\",\n"
        "    \"x_label\": \"X Axis Label\",\n"
        "    \"y_label\": \"Y Axis Label\",\n"
        "    \"data\": [\n"
        "        {{\"label\": \"2020\", \"value\": 100}},\n"
        "        {{\"label\": \"2021\", \"value\": 150}}\n"
        "    ]\n"
        "}}\n"
        "```\n"
        "Ensure the graph title and labels are in the same language as the answer. "
        "Do not include this JSON if the data is not suitable for a chart."
        "\n\n"
        "{context}"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
        ]
    )

    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

    return rag_chain

def get_all_documents(vector_store):
    """
    Retrieves all documents stored in the Chroma vector store.
    """
    # Chroma's get() method without arguments returns all data
    data = vector_store.get()

    documents = []
    # Combine the separate lists (ids, metadatas, documents) into a list of dicts
    if data and "ids" in data:
        for i, doc_id in enumerate(data["ids"]):
            doc_content = data["documents"][i] if data["documents"] else ""
            metadata = data["metadatas"][i] if data["metadatas"] else {}
            documents.append({
                "id": doc_id,
                "content": doc_content,
                "metadata": metadata
            })

    return documents

def generate_summary_charts(chain):
    """
    Generates summary charts for key financial metrics using the chain.
    """
    prompt_text = (
        "Analyze the uploaded financial documents. "
        "Identify key financial metrics available across the provided time periods (years or quarters). "
        "Specifically, attempt to generate the following charts if data is available: "
        "1. Revenue Trend (Line or Bar) - showing revenue over time. "
        "2. Net Profit Trend (Line or Bar) - showing net profit over time. "
        "3. Operating Expenses (Bar or Pie) - showing breakdown of expenses or trend. "
        "4. Assets vs Liabilities (Bar) - comparison for the latest period. "
        "\n\n"
        "Output ONLY the JSON objects for these charts. Do not output any conversational text. "
        "Use Swedish labels for the charts (e.g., 'Omsättning', 'Vinst', 'Tillgångar', 'Skulder')."
    )

    max_retries = 3
    base_delay = 5 # seconds

    for attempt in range(max_retries):
        try:
            response = chain.invoke({"input": prompt_text})
            answer = response['answer']

            chart_data_list = []
            json_matches = re.finditer(r'```json\s*(\{.*?\})\s*```', answer, re.DOTALL)

            for match in json_matches:
                json_str = match.group(1)
                try:
                    data = json.loads(json_str)
                    chart_data_list.append(data)
                except json.JSONDecodeError:
                    pass

            return chart_data_list
        except Exception as e:
            # Check for Rate Limit Error
            error_str = str(e)
            if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                if attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    print(f"Rate limit hit. Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    continue
                else:
                    print(f"Error generating summary charts (Max retries reached): {e}")
                    return []
            else:
                print(f"Error generating summary charts: {e}")
                return []
    return []
