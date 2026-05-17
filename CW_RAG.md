# ClarityWorks: The RAG System — Retrieval-Augmented Generation

**Files:** `ml-service/models/rag_engine.py`, `ml-service/app.py` (RAG endpoints), `frontend/src/components/RAG/`

---

## 1. What Is RAG?

**Retrieval-Augmented Generation (RAG)** is a technique that combines two AI capabilities:

1. **Retrieval**: Search a database of documents to find passages relevant to a user's question
2. **Generation**: Feed those passages to a Large Language Model (LLM) which synthesises a coherent answer

Without RAG, an LLM can only answer from its training data (which may be outdated or lack domain-specific knowledge). With RAG, the LLM answers based on *your specific documents* — a textbook, a manual, a set of lecture notes.

### Why RAG Instead of Just Feeding the Whole Document to the LLM?

LLMs have context window limits (e.g., 128K tokens for Llama 3.3). A 500-page textbook exceeds this. Even if it fit, the model would struggle to locate the specific paragraph that answers a question buried on page 347. RAG solves this by:

1. Pre-computing searchable "embeddings" for small text chunks
2. At query time, finding only the 5 most relevant chunks
3. Sending just those chunks + the question to the LLM

This is more accurate, faster, and cheaper than processing the entire document.

---

## 2. The ClarityWorks RAG Architecture

```
  Upload Phase                              Query Phase
  ━━━━━━━━━━━━                              ━━━━━━━━━━━

  PDF/DOCX File                             User's Question
       │                                          │
       ▼                                          ▼
  ┌──────────────┐                      ┌──────────────────┐
  │ Text Extract │                      │ Generate Query   │
  │ pdfplumber / │                      │ Embedding        │
  │ python-docx  │                      │ E5-small-v2      │
  └──────────────┘                      │ "query: " prefix │
       │                                └──────────────────┘
       ▼                                          │
  ┌──────────────┐                                ▼
  │ Chunk Text   │                      ┌──────────────────┐
  │ 1500 chars   │                      │ Stage 1: Embed   │
  │ 300 overlap  │                      │ Similarity Search│
  │ Recursive    │                      │ Top-20 candidates│
  │ splitting    │                      │ from ChromaDB    │
  └──────────────┘                      └──────────────────┘
       │                                          │
       ▼                                          ▼
  ┌──────────────┐                      ┌──────────────────┐
  │ Generate     │                      │ Stage 2: Keyword │
  │ Embeddings   │                      │ Retrieval (BM25) │
  │ E5-small-v2  │                      │ + Merge with     │
  │ "passage: "  │                      │ semantic results │
  │ prefix       │                      └──────────────────┘
  └──────────────┘                                │
       │                                          ▼
       ▼                                ┌──────────────────┐
  ┌──────────────┐                      │ Stage 3: Re-rank │
  │ Store in     │                      │ FlashRank cross- │
  │ ChromaDB     │                      │ encoder → Top-5  │
  │ (persistent) │                      └──────────────────┘
  └──────────────┘                                │
                                                  ▼
                                        ┌──────────────────┐
                                        │ Stage 4: Generate│
                                        │ Answer via LLM   │
                                        │ Fireworks AI     │
                                        │ Llama 3.3 70B    │
                                        │ [Source N] cites  │
                                        └──────────────────┘
                                                  │
                                                  ▼
                                          Answer + Sources
```

---

## 3. Upload Phase: How Documents Are Processed

### 3.1 Text Extraction

- **PDF files**: Extracted using **pdfplumber** (a Python library that reads PDF page objects). We use multiple extraction strategies per page (different `x_tolerance`, `y_tolerance`, `layout` settings, deduplication) and pick the highest-quality result based on a quality scoring function.
- **DOCX files**: Extracted using **python-docx** — straightforward paragraph-by-paragraph extraction.

The extracted text passes through `TextCleaner`:
- Unicode normalisation (smart quotes → ASCII, ligatures → letters like `ﬁ` → `fi`)
- PDF glyph repair (custom font characters → best-guess English letters using `wordfreq` dictionary scoring)
- Removal of page numbers, headers/footers, table of contents entries
- Joining of broken line wraps (PDF visual line breaks ≠ paragraph breaks)
- Bullet normalisation (various bullet characters → standard `- `)

### 3.2 Text Chunking

We use **RecursiveCharacterTextSplitter** from LangChain:

```python
self.text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=300,
    separators=["\n\n", "\n", ". ", " ", ""],
    keep_separator=True,
)
```

**How recursive splitting works:**

1. Try to split on `\n\n` (paragraph boundaries) — preserves paragraph coherence
2. If chunks are still too large, split on `\n` (line breaks)
3. If still too large, split on `. ` (sentence boundaries)
4. If still too large, split on ` ` (word boundaries)
5. Last resort: split on `""` (character boundaries)

**Why 1500 characters with 300 overlap?**
- 1500 chars ≈ 200-300 words — enough context for a meaningful passage
- 300-char overlap ensures sentences at chunk boundaries appear in both adjacent chunks, so a relevant sentence isn't missed because it was split across two chunks

### 3.3 Embedding Generation

Each chunk is converted to a **384-dimensional numerical vector** using the **E5-small-v2** model from `sentence-transformers`:

```python
passage_texts = ["passage: " + t for t in chunk_texts]
embeddings = self.embedding_model.encode(passage_texts)
```

**What are embeddings?** An embedding is a fixed-size vector of floating-point numbers that captures the semantic meaning of a text. Texts with similar meanings have vectors that are close together in 384-dimensional space (measured by Euclidean distance or cosine similarity).

**Why E5-small-v2?** It's a 33M-parameter model (small enough for CPU) that outperforms the more commonly used MiniLM on retrieval benchmarks. It requires `"passage: "` prefix for documents and `"query: "` prefix for queries — this asymmetric training makes it better at matching questions to answers.

### 3.4 Vector Storage: ChromaDB

ChromaDB is an embedded (in-process) vector database. Each document gets its own collection (`doc_{uuid}`). Chunks are stored with:
- The embedding vector
- The raw text
- Metadata: chunk_id, character count, word count, document_id, filename, page number

ChromaDB persists to disk at `ml-service/data/chromadb/`. On startup, the system checks a `.embedding_model` marker file — if the embedding model has changed since last run, all collections are cleared (because vectors from different models are incompatible).

---

## 4. Query Phase: How Questions Are Answered

### 4.1 Stage 1: Semantic Embedding Search

```python
query_embedding = self.embedding_model.encode(["query: " + query_text])[0]
results = collection.query(
    query_embeddings=[query_embedding.tolist()],
    n_results=20,  # Top 20 candidates per collection
)
```

The user's question is embedded with the `"query: "` prefix, and ChromaDB returns the 20 closest chunks by L2 (Euclidean) distance. Distance is converted to similarity: `similarity = max(0, min(1, 1 - distance/2))`.

### 4.2 Stage 2: Keyword Retrieval (Hybrid Search)

In addition to semantic search, the system performs **keyword-based retrieval**:

```python
def _keyword_score(self, query_text, document_text):
    # Tokenise both into content words (>2 chars, not stop words)
    # Compute: coverage (% of query terms found) * 0.75
    #        + phrase bonus (0.2 if full query phrase appears)
    #        + acronym bonus (0.05 per matching acronym)
    #        + term density bonus (up to 0.2)
```

This catches cases where the user asks about a specific term (e.g., "What is photosynthesis?") that might not be the closest embedding match but literally contains the exact word.

**Hybrid scoring**: `final_score = semantic_score * 0.7 + keyword_score * 0.3`

Duplicate candidates (same chunk from both methods) are merged, keeping the higher scores.

### 4.3 Stage 3: Cross-Encoder Re-Ranking (FlashRank)

The top candidates from Stage 1+2 are re-ranked using a **cross-encoder**:

```python
rerank_request = RerankRequest(query=query_text, passages=passages)
reranked = self.ranker.rerank(rerank_request)
```

**What is a cross-encoder?** Unlike the bi-encoder (E5-small-v2) which embeds query and document separately, a cross-encoder takes both query AND document as a single input and produces a relevance score. This is more accurate but slower — which is why we only run it on the top 20 candidates, not the entire collection.

**FlashRank** uses the `ms-marco-MiniLM-L-12-v2` model (~4MB, ONNX format, CPU-only). It was trained on the MS MARCO passage ranking dataset — millions of real search queries paired with relevant passages.

The top 5 after re-ranking are the final sources.

**Relevance labels:**
- Score >= 0.65: "Strong"
- Score >= 0.35: "Moderate"
- Below 0.35: "Weak"

### 4.4 Stage 4: Answer Generation (True RAG)

The final step is the "Generation" in RAG — synthesising a coherent answer:

```python
def _generate_answer(self, query, top_results):
    context_parts = []
    for i, result in enumerate(top_results, 1):
        source_text = f"[Source {i}]:\n{result['text']}"
        context_parts.append(source_text)

    prompt = f"""You are a knowledgeable textbook assistant.
    Answer ONLY from the provided textbook excerpts...
    QUESTION: {query}
    RELEVANT TEXTBOOK SECTIONS: {context}
    """
```

The LLM (Fireworks AI, `llama-v3p3-70b-instruct`) receives:
- The user's question
- The top-5 relevant chunks, labelled `[Source 1]` through `[Source 5]`
- Instructions to cite sources inline, not fabricate, and write in prose (not bullet points)

**Parameters**: `temperature=0.25` (mostly deterministic), `max_tokens=2500`, `top_p=0.9`

The response includes inline `[Source N]` citations so users can verify claims against the original text.

### 4.5 Fallback Behaviour

- If FlashRank fails to initialise (ONNX conflict), the system falls back to embedding similarity scores
- If the Fireworks API key is not configured, only sources are returned (no synthesised answer)
- The frontend shows a yellow warning when answer generation is disabled

---

## 5. The Return Format

```json
{
    "answer": "Photosynthesis is the process by which plants... [Source 1]. The light-dependent reactions... [Source 3].",
    "sources": [
        {
            "text": "The chunk text...",
            "metadata": {"filename": "biology.pdf", "page_number": "47", ...},
            "similarity_score": 0.82,
            "semantic_score": 0.82,
            "keyword_score": 0.45,
            "hybrid_score": 0.71,
            "rerank_score": 0.89,
            "relevance_score": 0.89,
            "relevance_label": "Strong"
        },
        ...
    ],
    "has_answer": true
}
```

---

## 6. PDF Extraction Quality System

ClarityWorks has a sophisticated PDF quality detection system because many PDFs use custom fonts that produce garbled text:

### Quality Metrics (`TextCleaner.pdf_extraction_quality_metrics`)

- **Replacement characters**: U+FFFD (the "?" diamond) indicates the PDF extractor couldn't decode a glyph
- **Suspicious glyphs**: Characters like Ô, Ɵ, Ō that are commonly produced when PDF fonts encode ligatures ("ti", "ft", "tf") as custom glyphs
- **Private Use Area characters**: Unicode range E000-F8FF used by PDF fonts for custom glyphs
- **Broken words**: Words containing suspicious glyphs (e.g., "moƟvaƟon" for "motivation")

### Glyph Repair

The `repair_extracted_glyphs()` method tries to fix broken words:

1. For each word containing suspicious glyphs, generate all possible letter combinations (e.g., Ɵ could be "ti")
2. Score each candidate using `wordfreq.zipf_frequency()` — real English words score higher
3. Pick the highest-scoring candidate if it scores >= 2.0 (a real word threshold)
4. Preserve original capitalisation

**Example**: "moƟvaƟon" → try "motivation", "moftvaƟon", "moƟvafton", "moftvafton" → "motivation" scores highest → accept

### Quality Labels

- **Clean**: No issues detected
- **Limited**: Fewer than 20 words extracted (page might be mostly images)
- **Degraded**: Contains suspicious glyphs or private-use characters

---

## 7. Frontend RAG Components

### RAGUpload.tsx
- File drop zone accepting PDF/DOCX up to 100MB
- Shows upload progress and chunk count after processing
- Displays extraction quality warnings if the PDF had issues

### RAGQuery.tsx
- Text input for natural language questions
- Document selector (choose which uploaded documents to search)
- Results display:
  - **Answer box**: Green/teal gradient box with Bot icon, showing the synthesised answer
  - **Source documents**: Expandable cards with chevron toggles, showing chunk text, similarity score badges, word counts, and page numbers
  - **Export**: PDF and DOCX export including the answer section

---

## 8. Key Libraries Used in RAG

| Library | Version | Role in RAG |
|---------|---------|-------------|
| **chromadb** | 0.4.22 | Embedded vector database, stores chunks + embeddings on disk |
| **sentence-transformers** | 2.3.1 | Loads E5-small-v2 for embedding generation |
| **flashrank** | 0.2+ | Cross-encoder re-ranking (ONNX, CPU-only, ~4MB) |
| **langchain-text-splitters** | 0.2+ | RecursiveCharacterTextSplitter for intelligent chunking |
| **pdfplumber** | 0.10.3 | PDF text extraction with multiple strategies |
| **python-docx** | 1.1.0 | DOCX text extraction |
| **openai** (SDK) | — | Client for Fireworks AI API (OpenAI-compatible endpoint) |
