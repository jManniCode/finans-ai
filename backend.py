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
    Splits the documents into chunks.
    """
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)
    return chunks

def create_vector_store(chunks):
    """
    Creates a Chroma vector store from the document chunks.
    """
    # Using the default model for GoogleGenerativeAIEmbeddings if not specified,
    # but explicitly 'models/embedding-001' is a safe bet for compatibility.
    # The user asked to use the default, so we'll instantiate it without arguments
    # or with the standard one if needed.
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

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
        "Format citations as [Page X]. Example: 'Revenue increased by 10% [Page 3]'. "
        "If the answer is not in the context, say that you don't know. "
        "Keep the answer concise."
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
