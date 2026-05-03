import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from flashrank import Ranker, RerankRequest
import os
import json


class RAGEngine:
    """
    Retrieval-Augmented Generation engine for textbook processing
    Uses ChromaDB (local vector database) + E5-small-v2 embeddings
    + FlashRank re-ranking + RecursiveCharacterTextSplitter chunking
    + Fireworks AI LLM for answer generation (True RAG)
    """

    EMBEDDING_MODEL_NAME = 'intfloat/e5-small-v2'

    def __init__(self):
        self.data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        self.embedding_cache_dir = os.path.join(self.data_dir, 'hf_cache')
        self.local_embedding_dir = os.path.join(self.embedding_cache_dir, 'intfloat-e5-small-v2')
        os.makedirs(self.embedding_cache_dir, exist_ok=True)

        # Initialize ChromaDB with persistent storage
        persist_dir = os.path.join(self.data_dir, 'chromadb')
        os.makedirs(persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )

        # Check if embedding model changed — if so, clear old incompatible data
        self._check_model_migration(persist_dir)

        # Load embedding model (e5-small-v2: 384 dims, much more accurate than MiniLM)
        print("Loading embedding model (e5-small-v2)...")
        embedding_source = self._get_embedding_source()
        self.embedding_model = SentenceTransformer(
            embedding_source,
            cache_folder=self.embedding_cache_dir,
        )
        print("Embedding model loaded!")

        # Initialize text splitter (replaces custom chunking)
        # Larger chunks (1500 chars) capture more context per retrieval hit,
        # producing richer answers without losing paragraph coherence.
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=300,
            separators=["\n\n", "\n", ". ", " ", ""],
            keep_separator=True,
        )

        # Initialize FlashRank re-ranker (~4MB, CPU-only, no PyTorch needed)
        print("Loading re-ranker model...")
        try:
            self.ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir=os.path.join(
                self.data_dir, 'flashrank_cache'
            ))
            print("Re-ranker loaded!")
        except Exception as e:
            print(f"FlashRank init failed, will use embedding similarity fallback: {e}")
            self.ranker = None

        # Initialize Fireworks AI client for answer generation (True RAG)
        self.llm_client = None
        fireworks_key = os.getenv('FIREWORKS_API_KEY')
        if fireworks_key:
            try:
                from openai import OpenAI
                self.llm_client = OpenAI(
                    base_url="https://api.fireworks.ai/inference/v1",
                    api_key=fireworks_key,
                )
                print("Fireworks client initialized for RAG answer generation")
            except Exception as e:
                print(f"Fireworks initialization failed: {e}")
        else:
            print("FIREWORKS_API_KEY not found - answer generation disabled")

    def _get_embedding_source(self):
        """Prefer repo-local model snapshots to avoid runtime network fetches."""
        required_files = ('config.json', 'modules.json')
        if all(os.path.exists(os.path.join(self.local_embedding_dir, name)) for name in required_files):
            return self.local_embedding_dir
        return self.EMBEDDING_MODEL_NAME

    def _check_model_migration(self, persist_dir):
        """Clear ChromaDB data if embedding model has changed (incompatible vectors)"""
        marker_path = os.path.join(persist_dir, '.embedding_model')

        current_model = self.EMBEDDING_MODEL_NAME
        previous_model = None

        if os.path.exists(marker_path):
            with open(marker_path, 'r') as f:
                previous_model = f.read().strip()

        if previous_model != current_model:
            if previous_model:
                print(f"Embedding model changed: {previous_model} -> {current_model}")
                print("Clearing old ChromaDB collections (incompatible vectors)...")
                try:
                    collections = self.client.list_collections()
                    for coll in collections:
                        self.client.delete_collection(coll.name)
                    print(f"Cleared {len(collections)} old collection(s)")
                except Exception as e:
                    print(f"Warning: Could not clear old collections: {e}")

            # Write new marker
            with open(marker_path, 'w') as f:
                f.write(current_model)

    def upload_document(self, document_id, text, metadata):
        """
        Chunk document, generate embeddings, store in ChromaDB

        Args:
            document_id: Unique ID (UUID)
            text: Full extracted text
            metadata: {'filename', 'user_id'}

        Returns:
            {'chunks_created', 'collection_id'}
        """
        print(f"Processing document {document_id}...")

        # Smart chunking with RecursiveCharacterTextSplitter
        chunk_texts = self.text_splitter.split_text(text)
        print(f"Created {len(chunk_texts)} chunks")

        # Create collection for this document
        collection_name = f"doc_{document_id}"
        collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"filename": str(metadata.get("filename", "")), "user_id": str(metadata.get("user_id", ""))}
        )

        # Generate embeddings with e5 prefix (required for e5 models)
        print("Generating embeddings...")
        passage_texts = ["passage: " + t for t in chunk_texts]
        embeddings = self.embedding_model.encode(passage_texts, show_progress_bar=True)

        # Store in ChromaDB
        print("Storing in vector database...")
        collection.add(
            embeddings=embeddings.tolist(),
            documents=chunk_texts,
            metadatas=[{
                'chunk_id': str(i),
                'char_count': str(len(chunk)),
                'word_count': str(len(chunk.split())),
                'document_id': document_id,
                'filename': str(metadata.get("filename", ""))
            } for i, chunk in enumerate(chunk_texts)],
            ids=[f"chunk_{i}" for i in range(len(chunk_texts))]
        )

        print(f"Document uploaded: {len(chunk_texts)} chunks stored")

        return {
            'chunks_created': len(chunk_texts),
            'collection_id': collection_name
        }

    def query_documents(self, query_text, document_ids=None, top_k=5):
        """
        Semantic search with re-ranking and answer generation (True RAG)

        Strategy:
        1. Retrieve top-20 candidates via embedding similarity
        2. Re-rank with FlashRank cross-encoder to get precise top-k
        3. Generate coherent answer from top-k using Fireworks AI LLM

        Args:
            query_text: Natural language query
            document_ids: List of doc IDs to search (None = all documents)
            top_k: Number of final results to return (after re-ranking)

        Returns:
            {
                'answer': AI-generated answer with citations (or None),
                'sources': List of top-k chunks with scores,
                'has_answer': bool
            }
        """
        print(f"Querying: '{query_text}'")

        # Generate query embedding with e5 prefix
        query_embedding = self.embedding_model.encode(["query: " + query_text])[0]

        # Determine which collections to search
        if document_ids:
            collection_names = [f"doc_{doc_id}" for doc_id in document_ids]
        else:
            all_collections = self.client.list_collections()
            collection_names = [c.name for c in all_collections]

        print(f"Searching {len(collection_names)} document(s)...")

        # Stage 1: Retrieve top-20 candidates per collection via embedding similarity
        candidates_per_collection = 20
        all_candidates = []

        for coll_name in collection_names:
            try:
                collection = self.client.get_collection(coll_name)
                collection_metadata = collection.metadata or {}

                results = collection.query(
                    query_embeddings=[query_embedding.tolist()],
                    n_results=min(candidates_per_collection, collection.count()),
                    include=['documents', 'metadatas', 'distances']
                )

                for i, doc in enumerate(results['documents'][0]):
                    distance = results['distances'][0][i]
                    similarity = max(0.0, min(1.0, 1 - (distance / 2)))
                    raw_metadata = results['metadatas'][0][i] or {}
                    merged_metadata = {
                        **raw_metadata,
                        'filename': raw_metadata.get('filename') or str(collection_metadata.get('filename', ''))
                    }

                    all_candidates.append({
                        'text': doc,
                        'metadata': merged_metadata,
                        'similarity_score': round(similarity, 4),
                        'collection': coll_name
                    })

            except Exception as e:
                print(f"Error querying collection {coll_name}: {e}")
                continue

        if not all_candidates:
            print("No candidates found")
            return {
                'answer': None,
                'sources': [],
                'has_answer': False
            }

        # Stage 2: Re-rank candidates with FlashRank cross-encoder
        print(f"Re-ranking {len(all_candidates)} candidates...")
        passages = [{"id": i, "text": c['text'], "meta": {
            "metadata": c['metadata'],
            "similarity_score": c['similarity_score'],
            "collection": c['collection']
        }} for i, c in enumerate(all_candidates)]

        if self.ranker is not None:
            try:
                rerank_request = RerankRequest(query=query_text, passages=passages)
                reranked = self.ranker.rerank(rerank_request)
                use_reranked = True
            except Exception as e:
                print(f"FlashRank re-ranking failed, falling back to embedding similarity: {e}")
                use_reranked = False
        else:
            use_reranked = False

        # Build final results from re-ranked order (or embedding similarity fallback)
        final_results = []
        if use_reranked:
            for item in reranked[:top_k]:
                meta = item.get("meta", {})
                final_results.append({
                    'text': item['text'],
                    'metadata': meta.get('metadata', {}),
                    'similarity_score': float(meta.get('similarity_score', 0)),
                    'rerank_score': round(float(item['score']), 4),
                    'collection': meta.get('collection', '')
                })
        else:
            all_candidates.sort(key=lambda c: c['similarity_score'], reverse=True)
            for c in all_candidates[:top_k]:
                final_results.append({
                    'text': c['text'],
                    'metadata': c['metadata'],
                    'similarity_score': float(c['similarity_score']),
                    'rerank_score': float(c['similarity_score']),
                    'collection': c['collection']
                })

        print(f"Returning top {len(final_results)} re-ranked results")

        # Stage 3: Generate answer from top results using Fireworks AI (True RAG)
        answer = None
        if self.llm_client and final_results:
            answer = self._generate_answer(query_text, final_results)

        return {
            'answer': answer,
            'sources': final_results,
            'has_answer': answer is not None
        }

    def _generate_answer(self, query, top_results):
        """
        Generate a coherent answer from retrieved chunks using Fireworks AI LLM.
        This is the "Generation" step in RAG — synthesizes information from
        multiple sources into a single answer with [Source N] citations.
        """
        if not self.llm_client:
            return None

        try:
            # Build context from top results
            context_parts = []
            for i, result in enumerate(top_results, 1):
                chunk_id = result['metadata'].get('chunk_id', 'N/A')
                source_text = f"[Source {i}] (Chunk {chunk_id}):\n{result['text']}"
                context_parts.append(source_text)

            context = "\n\n---\n\n".join(context_parts)

            prompt = f"""You are a knowledgeable textbook assistant. Your job is to provide comprehensive, well-structured answers based ONLY on the provided textbook excerpts.

QUESTION:
{query}

RELEVANT TEXTBOOK SECTIONS:
{context}

INSTRUCTIONS:
1. Write a thorough, detailed answer — aim for at least 3-4 substantial paragraphs when the sources contain enough material.
2. Open with a clear thesis or direct answer to the question in 1-2 sentences.
3. Then develop each major point in its own paragraph, explaining concepts fully rather than listing bullet points. Use examples, definitions, and elaborations from the source material.
4. Cite sources inline using [Source N] notation after each claim or paraphrase.
5. When the sources contain definitions, examples, or data, include them — they make the answer concrete.
6. If the question asks for a list or comparison, structure it clearly but still explain each item in depth.
7. End with a brief synthesis or conclusion that ties the key ideas together.
8. If the sources don't contain enough information, say so honestly, but still share whatever partial information IS available.
9. Do NOT fabricate information — only use what's in the sources.
10. Write in clear, flowing prose. Avoid choppy bullet-point lists when a paragraph would be more informative.

ANSWER:"""

            response = self.llm_client.chat.completions.create(
                model="accounts/fireworks/models/llama-v3p3-70b-instruct",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.25,
                max_tokens=2500,
                top_p=0.9
            )

            answer = response.choices[0].message.content.strip()
            print(f"Answer generated ({len(answer)} chars)")
            return answer

        except Exception as e:
            print(f"Answer generation error: {e}")
            return None

    def delete_document(self, document_id):
        """Delete document collection from ChromaDB"""
        try:
            collection_name = f"doc_{document_id}"
            self.client.delete_collection(collection_name)
            print(f"Deleted document collection: {collection_name}")
        except Exception as e:
            print(f"Error deleting collection: {e}")

    def get_all_collections(self):
        """Get list of all document collections"""
        return self.client.list_collections()
