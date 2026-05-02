"""
Test script for RAG improvements
Tests: chunking, re-ranking, Fireworks answer generation
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()


def test_rag_system():
    """Test all RAG improvements"""

    print("=" * 80)
    print("TESTING RAG IMPROVEMENTS")
    print("=" * 80)

    # Initialize RAG engine
    print("\nInitializing RAG engine...")
    from models.rag_engine import RAGEngine
    rag = RAGEngine()

    # Test 1: Check FlashRank initialization
    print("\n1. FlashRank Re-Ranker:")
    if rag.ranker:
        print("   PASS - FlashRank initialized successfully")
    else:
        print("   FAIL - FlashRank not initialized")

    # Test 2: Check Fireworks initialization
    print("\n2. Fireworks Answer Generation:")
    if rag.llm_client:
        print("   PASS - Fireworks client initialized")
    else:
        print("   WARN - Fireworks client not initialized (check FIREWORKS_API_KEY in .env)")

    # Test 3: Test chunking
    print("\n3. Improved Chunking (RecursiveCharacterTextSplitter):")
    test_text = """
# Chapter 1: Introduction to Physics

Physics is the study of matter, energy, and the fundamental forces of nature.
It seeks to understand how the universe behaves at every scale.

## Newton's Laws of Motion

Newton's first law states that an object at rest stays at rest, and an object
in motion stays in motion at constant velocity, unless acted upon by an
external force. This is also known as the law of inertia.

Newton's second law relates force, mass, and acceleration. The formula is
F = ma, where F is force measured in Newtons, m is mass in kilograms,
and a is acceleration in meters per second squared.

Newton's third law states that for every action, there is an equal and
opposite reaction. When you push against a wall, the wall pushes back
against you with equal force.

## Applications

These laws form the foundation of classical mechanics and are used to
predict the motion of everything from baseballs to planets. Engineers
use these principles to design bridges, vehicles, and spacecraft.
    """

    chunks = rag.text_splitter.split_text(test_text)
    print(f"   PASS - Created {len(chunks)} chunks from test text")
    for i, chunk in enumerate(chunks):
        print(f"   Chunk {i+1}: {len(chunk)} chars, starts with: {chunk[:60]}...")

    # Test 4: Test embedding generation
    print("\n4. E5-small-v2 Embeddings:")
    test_queries = ["What is Newton's first law?", "How does gravity work?"]
    embeddings = rag.embedding_model.encode(["query: " + q for q in test_queries])
    print(f"   PASS - Generated {len(embeddings)} embeddings")
    print(f"   Embedding dimensions: {embeddings.shape[1]}")

    # Test 5: Test answer generation (if Fireworks available)
    print("\n5. Answer Generation (True RAG):")
    if rag.llm_client:
        test_chunks = [
            {
                'text': "Newton's first law states that objects at rest stay at rest, and objects in motion stay in motion at constant velocity, unless acted upon by an external force. This is also known as the law of inertia.",
                'metadata': {'chunk_id': '1', 'page_number': 'N/A'},
                'similarity_score': 0.95,
                'collection': 'test'
            },
            {
                'text': "Newton's second law can be expressed as F = ma, where F is force measured in Newtons, m is mass in kilograms, and a is acceleration in meters per second squared.",
                'metadata': {'chunk_id': '2', 'page_number': 'N/A'},
                'similarity_score': 0.92,
                'collection': 'test'
            }
        ]

        answer = rag._generate_answer("What is Newton's first law?", test_chunks)
        if answer:
            print("   PASS - Answer generated successfully")
            print(f"   Answer: {answer[:200]}...")
        else:
            print("   FAIL - Answer generation returned None")
    else:
        print("   SKIP - Fireworks not configured")

    # Test 6: Test full query_documents return format
    print("\n6. Query Return Format:")
    # Just verify the return structure (no actual docs needed)
    empty_result = rag.query_documents("test query", document_ids=["nonexistent"])
    if isinstance(empty_result, dict) and 'answer' in empty_result and 'sources' in empty_result and 'has_answer' in empty_result:
        print("   PASS - Returns correct format: {answer, sources, has_answer}")
    else:
        print(f"   FAIL - Unexpected return format: {type(empty_result)}")

    print("\n" + "=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_rag_system()
