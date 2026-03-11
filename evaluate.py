import argparse
import json
import os
import pandas as pd
from datasets import Dataset
import plotly.express as px
from ragas import evaluate
from ragas.metrics import answer_relevancy, faithfulness, context_precision, context_recall

import backend

def load_evaluation_dataset(dataset_path):
    """
    Loads the evaluation dataset from a JSON file.
    The JSON should be a list of dictionaries with 'question' and 'ground_truth'.
    """
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data

def run_rag_pipeline(data, vector_store_path):
    """
    Runs the questions through the existing RAG pipeline and collects answers and contexts.
    """
    vector_store = backend.load_vector_store(vector_store_path)
    if not vector_store:
        raise ValueError(f"Could not load vector store from: {vector_store_path}")

    chain = backend.get_conversational_chain(vector_store)

    questions = []
    answers = []
    contexts_list = []
    ground_truths = []

    print("Running questions through RAG pipeline...")
    for item in data:
        question = item.get("question")
        ground_truth = item.get("ground_truth")

        if not question or not ground_truth:
            print(f"Skipping invalid item: {item}")
            continue

        try:
            # We use the chain to get the answer and the context
            # We need to extract the context documents as strings for Ragas
            response = chain.invoke({"input": question})
            answer = response["answer"]

            # Extract context strings
            context_docs = response.get("context", [])
            contexts = [doc.page_content for doc in context_docs]

            questions.append(question)
            answers.append(answer)
            contexts_list.append(contexts)
            # Ragas expects ground truth as a list of strings
            ground_truths.append(ground_truth)

        except Exception as e:
            print(f"Error processing question '{question}': {e}")

    return {
        "question": questions,
        "answer": answers,
        "contexts": contexts_list,
        "ground_truth": ground_truths
    }

def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG pipeline using Ragas.")
    parser.add_argument("--db-path", required=True, help="Path to the ChromaDB vector store directory.")
    parser.add_argument("--dataset-path", required=True, help="Path to the JSON dataset file.")
    parser.add_argument("--output", default="evaluation_results.html", help="Path to save the output Plotly graph (HTML).")
    args = parser.parse_args()

    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: GOOGLE_API_KEY is not set in the environment.")
        return

    try:
        # 1. Load Dataset
        print(f"Loading dataset from {args.dataset_path}...")
        raw_data = load_evaluation_dataset(args.dataset_path)

        # 2. Run RAG Pipeline
        print(f"Using vector store from {args.db_path}...")
        pipeline_results = run_rag_pipeline(raw_data, args.db_path)

        # 3. Create Hugging Face Dataset
        hf_dataset = Dataset.from_dict(pipeline_results)

        # 4. Run Ragas Evaluation
        print("Starting Ragas evaluation...")

        # In ragas 0.1.x, we need to explicitly provide the LLM and Embeddings to the evaluate function
        # We can try to use the ones defined in our backend, but it's safer to configure LangchainLLM
        # and LangchainEmbeddings wrappers if needed. For now, ragas can auto-detect from environment
        # but we are using Gemini. Let's explicitly pass the initialized LLM/Embeddings if possible,
        # or rely on the Ragas defaults configured via environment variables.
        # Since we use Google Gemini, let's configure Ragas to use it.

        from langchain_google_genai import ChatGoogleGenerativeAI

        eval_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
        eval_embeddings = backend.get_valid_embeddings()

        metrics = [
            answer_relevancy,
            faithfulness,
            context_precision,
            context_recall
        ]

        result = evaluate(
            dataset=hf_dataset,
            metrics=metrics,
            llm=eval_llm,
            embeddings=eval_embeddings
        )

        print("\nEvaluation Results:")
        print(result)

        # 5. Visualize Results
        print("\nGenerating visualization...")
        df = result.to_pandas()

        # We want to plot the aggregate scores across metrics
        # The 'result' object is essentially a dict of metric names to average scores
        # e.g., result = {'answer_relevancy': 0.8, 'faithfulness': 0.9, ...}

        # Prepare data for Plotly
        metrics_names = []
        scores = []
        for metric in metrics:
            metrics_names.append(metric.name)
            scores.append(result[metric.name])

        plot_df = pd.DataFrame({
            "Metric": metrics_names,
            "Score": scores
        })

        fig = px.bar(
            plot_df,
            x="Metric",
            y="Score",
            title="RAG Evaluation Metrics (Ragas)",
            color="Score",
            color_continuous_scale="Viridis",
            range_y=[0, 1]
        )

        fig.write_html(args.output)
        print(f"Evaluation visualization saved to {args.output}")

    except Exception as e:
        print(f"An error occurred during evaluation: {e}")

if __name__ == "__main__":
    main()
