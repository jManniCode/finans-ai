import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
try:
    from langchain.chains import create_retrieval_chain
    from langchain.chains.combine_documents import create_stuff_documents_chain
except ImportError:
    from langchain_classic.chains import create_retrieval_chain
    from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

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

    return chunks

def get_valid_embeddings():
    """
    Attempts to find a working embedding model by testing available options.
    """
    candidate_models = ["models/text-embedding-004", "models/embedding-001"]

    for model_name in candidate_models:
        try:
            embeddings = GoogleGenerativeAIEmbeddings(model=model_name)
            # Test the embeddings
            embeddings.embed_query("test")
            print(f"Successfully selected embedding model: {model_name}")
            return embeddings
        except Exception as e:
            print(f"Failed to initialize model {model_name}: {e}")
            continue

    # Fallback to default if everything fails (or let it crash with a clear error)
    print("Could not verify any specific model, falling back to 'models/embedding-001'")
    return GoogleGenerativeAIEmbeddings(model="models/embedding-001")

def create_vector_store(chunks):
    """
    Creates a Chroma vector store from the document chunks.
    """
    embeddings = get_valid_embeddings()

    # Create vector store in memory
    vector_store = Chroma.from_documents(chunks, embeddings)
    return vector_store

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
        "If the answer includes financial figures suitable for a visualization (e.g., trends over years, or comparisons between periods like Q3 2024 vs Q3 2025), "
        "or if the user explicitly asks for a graph, you MUST generate a JSON object representing this data at the very end of your response. "
        "Even for simple comparisons (e.g., This Year vs Last Year), generate a bar chart. "
        "The JSON must be enclosed in triple backticks with 'json' identifier, like this:\n"
        "```json\n"
        "{{\n"
        "    \"type\": \"bar\" or \"line\",\n"
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
