#!/usr/bin/env python3
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import os
import argparse
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_core.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from dotenv import load_dotenv
from tqdm import tqdm

def create_document(row):
    """Create a Document object from a DataFrame row."""
    content = f"Type: {row['type']}\n"
    content += f"Period: {row['start_date']} to {row['end_date']}\n"
    content += f"Ticker: {row['ticker']}\n"
    content += f"Growth (last day): {row['growth_last_day']:.2%}\n"
    content += f"Weekly Return: {row['weekly_return']:.2%}\n"
    content += f"Market Daily Return: {row['market_daily_return']:.2%}\n"
    content += f"Market Weekly Return: {row['market_weekly_return']:.2%}\n"
    content += f"Growth Above Market: {row['growth_above_market']:.2%}\n"
    content += f"Count: {row['count']}\n"
    content += f"Content: {row['text']}"
    
    return Document(
        page_content=content,
        metadata={
            'type': row['type'],
            'ticker': row['ticker'],
            'link': row['link'],
            'start_date': str(row['start_date']),
            'end_date': str(row['end_date']),
            'weekly_return': row['weekly_return'],
            'market_daily_return': row['market_daily_return'],
            'market_weekly_return': row['market_weekly_return'],
            'growth_above_market': row['growth_above_market']
        }
    )

def setup_qa_chain(documents):
    """Set up the QA chain with the given documents."""
    # Initialize text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    
    # Split documents
    splits = text_splitter.split_documents(documents)
    
    # Initialize embeddings and vector store
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(splits, embeddings)
    
    # Initialize LLM
    llm = ChatOpenAI(model_name="gpt-4", temperature=0)
    
    # Create prompt template
    prompt = PromptTemplate(
        template="""You are a financial news analyst assistant. Your task is to provide accurate, 
                well-structured responses based on the provided news articles context. Present the 
                information in chronological order, from earliest to most recent events.

                Format each section with a concise header showing period and performance:
                [YYYY-MM-DD..YYYY-MM-DD, +/-X.X% vs market]

                For individual stocks:
                1. Start each section with the period and growth header format shown above
                2. Follow with key developments and context during that period
                3. Include weekly returns comparison (stock vs market) if significant
                4. Explain what drove the performance

                For market-wide analysis:
                1. Use the same chronological structure with period headers
                2. Highlight notable sector or stock-specific movements
                3. Include market-wide return metrics when relevant

                Example format:
                [2024-01-01..2024-01-07, +2.3% vs market]
                Key developments and analysis...

                [2024-01-08..2024-01-14, -1.5% vs market]
                Key developments and analysis...

                Keep each section concise and focused. Do not exceed the line length of 80 
                characters to ensure readability.

                Structure your response to tell a compelling story, even without showing sources.
                Focus on chronological progression while maintaining accuracy and including all 
                key metrics.

                USE ONLY FACTS YOU SEE IN THE NEWS, DO NOT HALLUCINATE. If details are missing,
                omit them or state that the information is not available.

                Question: {question}
                Context: {context}

                Answer: Let's analyze this based on the provided information.""",
        input_variables=["context", "question"]
    )
    
    # Create and return chain
    chain = (
        {"context": vectorstore.as_retriever(search_kwargs={"k": 7}), "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return chain, vectorstore.as_retriever(search_kwargs={"k": 7})

def get_response(chain, retriever, query):
    """Get response using the RAG chain."""
    response = chain.invoke(query)
    sources = retriever.invoke(query)
    return response, sources

def print_sources(sources):
    """Print source documents in a formatted way."""
    print("\nSource Documents:")
    for i, doc in enumerate(sources, 1):
        print(f"\nSource {i}:")
        print(f"Type: {doc.metadata['type']}")
        print(f"Ticker: {doc.metadata['ticker']}")
        print(f"Period: {doc.metadata['start_date']} to {doc.metadata['end_date']}")
        print(f"Link: {doc.metadata['link']}")
        print(f"Weekly Return: {doc.metadata['weekly_return']:.2%}")
        print(f"Market Weekly Return: {doc.metadata['market_weekly_return']:.2%}")
        print(f"Growth Above Market: {doc.metadata['growth_above_market']:.2%}")

def main():
    parser = argparse.ArgumentParser(description='Analyze financial news based on your question')
    parser.add_argument('question', help='Question to analyze (e.g., "What are the latest developments for NVDA?")')
    parser.add_argument('--show_sources', help='Show source documents (optional)', type=lambda x: x.lower() == 'true', default=True)
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()
    
    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Load the data
    df = pd.read_parquet('data/news_feed_with_market_stats.parquet')
    
    # Create documents from all data
    documents = [create_document(row) for _, row in df.iterrows()]
    
    # Setup chain
    chain, retriever = setup_qa_chain(documents)
    
    # Get response
    response, sources = get_response(chain, retriever, args.question)
    
    # Calculate date range from relevant documents
    dates = [(doc.metadata['start_date'], doc.metadata['end_date']) for doc in sources]
    min_date = min(date[0] for date in dates)
    max_date = max(date[1] for date in dates)
    weeks = round((pd.to_datetime(max_date) - pd.to_datetime(min_date)).days / 7)
    
    # Determine if this is a ticker-specific analysis
    ticker_sources = [doc for doc in sources if doc.metadata['type'] == 'individual']
    if ticker_sources:
        # Get the most common ticker from individual sources
        tickers = [doc.metadata['ticker'] for doc in ticker_sources]
        if tickers:
            most_common_ticker = max(set(tickers), key=tickers.count)
            print(f"\nLong term news for {most_common_ticker} in the last {weeks} weeks ({min_date}..{max_date}):\n")
        else:
            print(f"\nAnalysis for the last {weeks} weeks ({min_date}..{max_date}):\n")
    else:
        print(f"\nAnalysis for the last {weeks} weeks ({min_date}..{max_date}):\n")
    
    print(response)
    
    # Print sources if requested
    if args.show_sources:
        print_sources(sources)

if __name__ == "__main__":
    main()
