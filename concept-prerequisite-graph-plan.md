# Concept Prerequisite Graph — Implementation Plan

## Context

ClarityWorks analyzes text readability but currently only reports *how hard* text is — not *why* it's hard from a knowledge perspective. The Concept Prerequisite Graph fills this gap: it models the knowledge structure of a text, showing "you need to understand X and Y before this text makes sense." This appears in **two places**:

1. **Analysis Results** — concept graph for the analyzed text passage
2. **RAG Documents** — concept graph for an uploaded textbook (whole-document knowledge map)

Both use the same `ConceptExtractor` class and the same `ConceptGraph.tsx` React Flow component.

---

## Architecture Overview

```
                    Analysis Results                    RAG Document View
                    (short text)                        (full textbook)
                         │                                    │
     POST /api/analyses/:id/concepts          POST /api/rag/documents/:id/concepts
                         │                                    │
              Backend fetches                     Backend fetches chunks
              original_text from DB               from ML service (ChromaDB)
                         │                                    │
                         └──────────┐    ┌────────────────────┘
                                    ▼    ▼
                          ML Service: /concepts/extract
                          (spaCy noun phrases + Fireworks LLM)
                                    │
                                    ▼
                          Returns {concepts, edges}
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
         Saved to analyses.concept_graph   Saved to rag_documents.concept_graph
                    │                               │
                    ▼                               ▼
            ConceptGraph.tsx                 ConceptGraph.tsx
            (same component)                (same component)
```

---

## Implementation Steps

### Step 1: ML Service — `ml-service/models/concept_extractor.py` (new file)

Create `ConceptExtractor` class following the `LLMValidator` pattern in [llm_validator.py](ml-service/models/llm_validator.py):

- **Init**: Fireworks client via `OpenAI(base_url=..., api_key=...)`, same as `llm_validator.py:11-21`
- **`extract(text)` method**: Works for both short analysis text and longer document text
  1. Run spaCy `en_core_web_sm` (already loaded elsewhere) to extract noun phrases. Deduplicate, rank by frequency, take top 20-30.
  2. Single Fireworks LLM call: send text (truncated to ~4000 chars) + noun phrases. Temperature=0.1, max_tokens=1500.
  3. Parse JSON response: strip markdown code blocks, `json.loads()`, fallback `None` — reuse pattern from `llm_validator.py:105-117`
  4. Validate: ensure concept IDs are unique, edges reference existing IDs, remove orphan nodes

- **`extract_from_chunks(chunks)` method**: For RAG documents where text is already chunked
  1. Concatenate chunks (cap at ~6000 chars — sample first, middle, last chunks for long documents)
  2. Extract noun phrases from ALL chunks with spaCy (captures full document vocabulary)
  3. Call same LLM prompt with the sampled text + all noun phrases
  4. Returns same `{concepts, edges}` structure

**LLM Prompt** (single-shot, structured JSON output):
```
Extract 5-15 key concepts from this text and map prerequisite dependencies.
For each concept, identify what prior knowledge a reader needs.

Return ONLY valid JSON:
{
  "concepts": [
    {"id": "c1", "label": "Backpropagation", "tier": "target", "description": "Algorithm for training neural networks"},
    {"id": "c2", "label": "Chain Rule", "tier": "intermediate", "description": "..."},
    {"id": "c3", "label": "Derivatives", "tier": "prerequisite", "description": "..."}
  ],
  "edges": [
    {"from": "c3", "to": "c2", "relationship": "required_for"}
  ]
}

Tiers: prerequisite = foundational knowledge assumed by the text
       intermediate = bridging concepts connecting prerequisites to targets
       target = main concepts the text teaches
Edges: flow from simpler → more complex (prerequisite → dependent)
```

### Step 2: ML Service — New endpoint in `ml-service/app.py`

Add `POST /concepts/extract`:
- Accepts `{"text": "...", "chunks": [...]}` — either `text` (analysis) or `chunks` (RAG)
- If `chunks` provided, calls `extract_from_chunks(chunks)`; otherwise calls `extract(text)`
- Validates text length (min 200 chars)
- Returns `{"success": true, "concept_graph": {...}}` or `{"concept_graph": null}` on failure

Also add `GET /rag/documents/<doc_id>/chunks`:
- Returns all chunks for a document from ChromaDB (the `ConceptExtractor` needs the actual text)
- This endpoint already has precedent — `rag_engine.py` can retrieve collection data

### Step 3: Database — Add columns in `backend/src/config/database.ts`

Two column additions using the existing `DO $$` migration pattern (line 34-48):

```sql
-- On analyses table
IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
  WHERE table_name = 'analyses' AND column_name = 'concept_graph') THEN
  ALTER TABLE analyses ADD COLUMN concept_graph JSONB;
END IF;

-- On rag_documents table
IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
  WHERE table_name = 'rag_documents' AND column_name = 'concept_graph') THEN
  ALTER TABLE rag_documents ADD COLUMN concept_graph JSONB;
END IF;
```

### Step 4: Backend — Analysis concept graph endpoint

In [analysisController.ts](backend/src/controllers/analysisController.ts), add `generateConceptGraph`:
1. Get analysis by ID, verify user owns it (same auth pattern as `getAnalysisById` at line 195)
2. Fetch `original_text` from the row
3. POST to `${PYTHON_SERVICE_URL}/concepts/extract` with `{text: original_text}`
4. UPDATE: `SET concept_graph = $1 WHERE id = $2`
5. Return `{success: true, conceptGraph: data}`

Update `getAnalysisById` (line 214-248): add `conceptGraph: row.concept_graph` to response.

Add route in [analysisRoutes.ts](backend/src/routes/analysisRoutes.ts): `router.post('/:id/concepts', generateConceptGraph)`

### Step 5: Backend — RAG concept graph endpoint

In [ragController.ts](backend/src/controllers/ragController.ts), add `generateDocumentConceptGraph`:
1. Get document by ID, verify user owns it
2. Fetch chunks from ML service: `GET ${PYTHON_SERVICE_URL}/rag/documents/${chromadb_collection_id}/chunks`
3. POST to `${PYTHON_SERVICE_URL}/concepts/extract` with `{chunks: [...]}`
4. UPDATE: `SET concept_graph = $1 WHERE id = $2` on `rag_documents`
5. Return `{success: true, conceptGraph: data}`

Add `getDocumentConceptGraph` to return saved graph data.

Add routes in [ragRoutes.ts](backend/src/routes/ragRoutes.ts):
- `router.post('/documents/:id/concepts', generateDocumentConceptGraph)`
- `router.get('/documents/:id/concepts', getDocumentConceptGraph)`

### Step 6: Frontend — Install dependencies

```
cd frontend && npm install @xyflow/react dagre @types/dagre
```

- `@xyflow/react` (React Flow v12): Interactive graph with custom nodes, directed edges, zoom/pan
- `dagre`: Hierarchical layout algorithm for automatic top-to-bottom node positioning

### Step 7: Frontend — TypeScript types in `frontend/src/types/index.ts`

```typescript
interface ConceptNode {
  id: string;
  label: string;
  tier: 'prerequisite' | 'intermediate' | 'target';
  description: string;
}

interface ConceptEdge {
  from: string;
  to: string;
  relationship: string;
}

interface ConceptGraph {
  concepts: ConceptNode[];
  edges: ConceptEdge[];
}
```

Update existing types: add `conceptGraph?: ConceptGraph | null` to the analysis response type.

### Step 8: Frontend — API methods in `frontend/src/services/api.ts`

Add to `analysisApi`:
```typescript
generateConceptGraph: (id: number) => api.post(`/api/analyses/${id}/concepts`)
```

Add to `ragApi`:
```typescript
generateConceptGraph: (id: number) => api.post(`/api/rag/documents/${id}/concepts`)
getConceptGraph: (id: number) => api.get(`/api/rag/documents/${id}/concepts`)
```

### Step 9: Frontend — `frontend/src/components/Analysis/ConceptGraph.tsx` (new file)

Shared component used by both Analysis and RAG. Props: `conceptGraph`, `onGenerate`, `loading`.

**Layout:**
- Collapsible card section matching existing card pattern
- If no graph: "Generate Concept Graph" button with Network icon
- If loading: spinner (2-5s for LLM call)
- If data: React Flow canvas with dagre hierarchical layout

**Node styling by tier** (matches the mockup):
- Prerequisite: dark blue/purple (`#1e3a5f`) — "you need this first"
- Intermediate: green (`#2d6a4f`) — bridging concepts
- Target: orange (`#e76f51`) — what the text teaches

**Features:**
- Legend showing three tier colors
- Nodes are draggable
- Tooltip on hover showing concept description
- Zoom/pan controls
- Dark mode compatible
- Caption: "Arrows mean 'is required before'. The graph shows what a reader must already know."

### Step 10: Frontend — Integrate into AnalysisResults.tsx

Add `ConceptGraph` component in [AnalysisResults.tsx](frontend/src/components/Analysis/AnalysisResults.tsx) as a new section (after charts, before improvement suggestions). Pass `analysisId` and `conceptGraph` from loaded data. The `onGenerate` callback calls `analysisApi.generateConceptGraph(id)`.

### Step 11: Frontend — Integrate into RAG

**Option A (recommended): Add to RAGUpload.tsx document list**

Each document card in [RAGUpload.tsx](frontend/src/components/RAG/RAGUpload.tsx) gets a "Concept Map" button (Network icon). Clicking it:
1. Calls `ragApi.generateConceptGraph(docId)` (or loads saved graph via `getConceptGraph`)
2. Renders `ConceptGraph` component in a modal or expandable section below the document card

This keeps the feature discoverable without needing a new page.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Fireworks API key missing | Returns `null`. Button shows disabled with tooltip |
| Rate limited | Single retry with backoff, then `null`. Show "Try again" |
| Bad JSON from LLM | Parse failure caught, return `null`. Show "Could not generate" |
| Text too short (<200 chars) | Return `null` without LLM call |
| Very long document | Sample chunks (first + middle + last, ~6000 chars total) + extract noun phrases from ALL chunks |

---

## Files to Create
- `ml-service/models/concept_extractor.py` — ConceptExtractor class
- `frontend/src/components/Analysis/ConceptGraph.tsx` — React Flow graph component (shared)

## Files to Modify
- `ml-service/app.py` — add `/concepts/extract` endpoint + `/rag/documents/<id>/chunks` endpoint
- `ml-service/models/rag_engine.py` — add `get_document_chunks(doc_id)` method
- `backend/src/config/database.ts` — add `concept_graph JSONB` to both `analyses` and `rag_documents`
- `backend/src/controllers/analysisController.ts` — add `generateConceptGraph`, update `getAnalysisById` response
- `backend/src/routes/analysisRoutes.ts` — add `POST /:id/concepts`
- `backend/src/controllers/ragController.ts` — add `generateDocumentConceptGraph`, `getDocumentConceptGraph`
- `backend/src/routes/ragRoutes.ts` — add `POST/GET /documents/:id/concepts`
- `frontend/src/types/index.ts` — add ConceptGraph types
- `frontend/src/services/api.ts` — add concept graph API methods to both `analysisApi` and `ragApi`
- `frontend/src/components/Analysis/AnalysisResults.tsx` — integrate ConceptGraph component
- `frontend/src/components/RAG/RAGUpload.tsx` — add concept map button per document

## New Dependencies
| Package | Layer | Purpose |
|---------|-------|---------|
| `@xyflow/react` | Frontend | Interactive graph visualization |
| `dagre` | Frontend | Hierarchical layout algorithm |
| `@types/dagre` | Frontend (dev) | TypeScript types |

## Verification
1. **Analysis flow**: Analyze a scientific text (biology/CS) → click "Generate Concept Graph" → verify graph renders with correct tiers and edges → reload page → graph persists
2. **RAG flow**: Upload a textbook PDF → click "Concept Map" on the document → verify graph extracts document-wide concepts → verify it persists
3. **Graceful degradation**: Remove Fireworks API key → verify buttons disabled/show message → analysis still works normally
4. **Dark mode**: Toggle dark mode → verify nodes and edges remain readable
5. **Edge cases**: Short text (<200 chars), narrative text (fewer concepts), very long document
