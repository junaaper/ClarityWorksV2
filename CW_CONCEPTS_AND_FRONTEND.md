# ClarityWorks: Concept Graphs, Frontend, Authentication & Database

**Files:** `ml-service/models/concept_extractor.py`, `frontend/src/components/Analysis/ConceptGraph.tsx`, all frontend components, `backend/src/middleware/auth.ts`, `backend/src/config/database.ts`

---

## 1. Concept Prerequisite Graphs

### 1.1 What Is a Concept Prerequisite Graph?

A concept prerequisite graph is a directed graph that maps the knowledge a reader **needs before** they can understand a piece of text. It answers: "What must someone already know to make sense of this passage?"

Each node is a **concept** (e.g., "Photosynthesis", "Light Energy", "Chloroplast"), and each edge means "this concept is required before that concept." The graph shows readers — and educators — exactly where gaps in prior knowledge might trip someone up.

### 1.2 The Three Concept Tiers

Concepts are classified into three tiers, each represented by a different colour in the UI:

| Tier | Colour | Meaning |
|------|--------|---------|
| **Prerequisite** | Blue (`#1e3a5f` bg, `#3b82f6` border) | Foundational knowledge the text **assumes** the reader already has |
| **Intermediate** | Green (`#2d6a4f` bg, `#22c55e` border) | Bridging concepts that connect prerequisites to the main ideas |
| **Target** | Orange (`#9a3412` bg, `#f97316` border) | The main concepts the text is **actively teaching** |

Edges always flow from simpler to more complex: prerequisite → intermediate → target. This creates a hierarchy from bottom (what you need) to top (what the text teaches).

### 1.3 Backend: ConceptExtractor (`concept_extractor.py`)

**File:** `ml-service/models/concept_extractor.py` (262 lines)

The `ConceptExtractor` class uses a two-stage pipeline: **spaCy noun phrase extraction** followed by **LLM-based concept/edge generation** via Fireworks AI.

#### Stage 1: Noun Phrase Extraction (`_extract_noun_phrases`)

```python
doc = nlp(text[:50000])   # spaCy processes up to 50K chars

phrase_counts = Counter()
for chunk in doc.noun_chunks:
    phrase = chunk.text.strip().lower()
    # Filter: 3+ chars, ≤5 words, not a pronoun/determiner
    # Skip: 'this', 'that', 'it', 'they', 'he', 'she', etc.
    # Skip: chunks where ALL tokens are DET/PRON/ADP
    phrase_counts[phrase] += 1

# Return top 30 by frequency
ranked = sorted(phrase_counts.items(), key=lambda x: x[1], reverse=True)
return [phrase for phrase, _ in ranked[:30]]
```

**How it works:**
1. spaCy parses the text into a dependency tree for each sentence
2. `doc.noun_chunks` yields spans identified as noun phrases by spaCy's dependency parser
3. We count how often each phrase appears — frequent noun phrases are likely key concepts
4. We filter out pronouns, determiners, and very short/long phrases
5. The top 30 most-frequent noun phrases are passed to the LLM as "hints"

**Why extract noun phrases first?** The LLM receives the text plus a curated list of candidate concepts. Without these hints, the LLM might focus on irrelevant details or miss domain-specific terms. The noun phrases act as structured guidance — the LLM can use them or ignore them, but they steer it toward the text's actual terminology.

#### Stage 2: LLM Concept Generation (`_call_llm`)

The extracted noun phrases and the text (truncated to 4,000 characters) are sent to Fireworks AI (Llama 3.3 70B):

```python
prompt = """You are analyzing a text to build a concept prerequisite graph.
A concept prerequisite graph shows what knowledge a reader needs before
they can understand the main ideas.

TEXT: {text}

KEY NOUN PHRASES FOUND: {phrases}

TASK: Extract 5-15 key concepts from this text and map their prerequisite
dependencies. For each concept, identify what prior knowledge a reader
needs to understand it.

Return ONLY valid JSON:
{
  "concepts": [
    {"id": "c1", "label": "Short Name", "tier": "target", "description": "..."},
    ...
  ],
  "edges": [
    {"from": "c3", "to": "c1", "relationship": "required_for"},
    ...
  ]
}
"""
```

**LLM parameters:** `temperature=0.1` (near-deterministic for consistent structure), `max_tokens=1500`

**Rules enforced by the prompt:**
- 5-15 concepts total
- Labels are 1-3 words
- Every concept must have at least one edge connection
- Every edge `from`/`to` must reference a valid concept ID
- Edges flow from simpler → more complex

#### Stage 3: JSON Parsing (`_parse_json_response`)

The LLM sometimes wraps its response in markdown code blocks despite being told not to. The parser handles this:

1. Strip markdown fences (` ```json ... ``` `)
2. Try `json.loads()` on the cleaned string
3. If that fails, find the first `{` and last `}` and try parsing that substring
4. If all parsing fails, return `None` and log the error

#### Stage 4: Graph Validation (`_validate_graph`)

After parsing, the graph goes through validation:

1. **Check concept structure**: each concept must have `id` and `label`; invalid `tier` values default to `intermediate`
2. **Validate edges**: both `from` and `to` must reference existing concept IDs; self-loops are removed
3. **Remove disconnected concepts**: any concept that appears in zero edges is dropped — it would float as an isolated node with no meaning in the graph
4. **Minimum threshold**: must have at least 2 connected concepts and 1 edge, otherwise return `None`

#### Chunk Sampling for RAG Documents (`extract_from_chunks`)

For RAG documents (which may have hundreds of chunks), processing all text would exceed LLM context limits. The system uses strategic sampling:

```python
def _sample_chunks(self, chunks, max_chars=6000):
    indices = [0, total // 2, total - 1]  # Start, middle, end
    if total > 6:
        indices.extend([total // 4, 3 * total // 4])  # Add quartiles
```

This samples 3-5 representative chunks from evenly spaced positions in the document — beginning, quarter, middle, three-quarter, and end — capturing the document's full conceptual arc within a 6,000-character budget.

### 1.4 Frontend: ConceptGraph.tsx (269 lines)

**File:** `frontend/src/components/Analysis/ConceptGraph.tsx`

The frontend renders the concept graph as an interactive, draggable node-edge diagram using **ReactFlow** with automatic layout computed by **dagre**.

#### Automatic Layout with dagre

**dagre** is a directed graph layout algorithm library. It positions nodes in a hierarchical tree/DAG structure automatically:

```typescript
const g = new dagre.graphlib.Graph();
g.setGraph({
  rankdir: 'TB',      // Top-to-Bottom layout (prerequisites at top)
  nodesep: 70,        // Horizontal spacing between nodes
  ranksep: 80,        // Vertical spacing between ranks
  marginx: 20,
  marginy: 20,
});
```

**`rankdir: 'TB'`** means the graph flows top-to-bottom. Prerequisites appear at the top, intermediate concepts in the middle, and target concepts at the bottom. This creates a natural reading direction: "start at the top with what you need to know, flow down to what the text teaches."

Each concept node has fixed dimensions: `NODE_WIDTH = 170`, `NODE_HEIGHT = 52`. dagre uses these dimensions to compute non-overlapping positions.

#### Custom ConceptNode Component

Each node is a custom ReactFlow node with:
- **Colour-coded background and border** based on tier (blue/green/orange)
- **Hover tooltip** showing the concept's one-sentence description (positioned above the node, appears on hover via CSS `group-hover:opacity-100`)
- **Connection handles** at top (target/input) and bottom (source/output) for edges
- **Text clamping**: labels are limited to 2 lines with `WebkitLineClamp: 2` and ellipsis overflow

#### Edge Styling

Edges are animated (dashed flowing lines) and colour-coded to match their source node's tier:
- From a prerequisite node → blue edge
- From an intermediate node → green edge
- From a target node → orange edge

Each edge has an arrow marker at the target end (`MarkerType.ArrowClosed`).

#### User Interactions

- **Generate button**: Appears when no graph exists; triggers the backend concept extraction
- **Regenerate button**: Appears after a graph is generated; re-runs extraction for a fresh result
- **Loading state**: Shows a spinner with "Extracting concepts and mapping prerequisites..."
- **Collapsible section**: The entire graph section has a chevron toggle (expanded by default)
- **Drag**: Nodes are draggable (`draggable: true`) — users can rearrange the layout
- **Zoom**: ReactFlow provides zoom controls (0.3x to 2x)
- **Pan**: Click and drag on the background to pan
- **Legend**: Colour-coded tier labels appear above the graph: "you need this first" (blue), "intermediate concept" (green), "target concept" (orange)
- **Tier counts**: The section header shows "N concepts, M dependencies"

#### Where Concept Graphs Appear

Concept graphs can be generated in two places:
1. **Analysis results page** — for any analysed text, via `analysisApi.generateConceptGraph(id)`
2. **RAG documents** — for any uploaded textbook, via `ragApi.generateConceptGraph(id)`

Both use the same `ConceptGraphSection` component. The `concept_graph` JSONB column exists on both the `analyses` and `rag_documents` database tables.

---

## 2. Frontend Architecture

### 2.1 Technology Stack

| Technology | Version | Role |
|-----------|---------|------|
| **React** | 18.2 | Component-based UI framework |
| **TypeScript** | 5.2 | Static typing for all frontend code |
| **Vite** | 5.0 | Build tool and development server (port 5173) with Hot Module Replacement |
| **TailwindCSS** | 3.3 | Utility-first CSS framework |
| **Recharts** | 2.10 | Charting library (LineChart, RadarChart, BarChart, PieChart) |
| **ReactFlow** (`@xyflow/react`) | — | Interactive node-edge graph rendering |
| **dagre** | — | Automatic directed graph layout algorithm |
| **Axios** | 1.6 | HTTP client with JWT interceptor |
| **React Router** | 6.21 | Client-side routing |
| **react-hook-form** | 7.49 | Form handling (login, register) |
| **lucide-react** | 0.294 | Icon library (100+ icons used throughout) |
| **jsPDF** | 2.5 | Client-side PDF report generation |
| **jspdf-autotable** | 3.8 | PDF table generation for reports |
| **docx** | 8.5 | Client-side DOCX document generation |
| **file-saver** | 2.0 | File download utility for DOCX export |

### 2.2 Application Routes (App.tsx)

All routes are defined in `App.tsx` using React Router v6:

```
/login              → Login page (public)
/register           → Register page (public)
/                   → Redirects to /dashboard
/dashboard          → Dashboard (stats, trend chart, recent analyses)
/analyze            → TextInput (5-tab text input)
/analysis/:id       → AnalysisResults (full results page)
/simplify/:analysisId → SimplifyPage (text rewrite workbench)
/rag/upload         → RAGUpload (textbook file upload)
/rag/query          → RAGQuery (natural language Q&A)
/compare            → ComparePage (side-by-side text comparison)
/batch              → BatchPage (batch text analysis)
/history            → History (tabbed: analyses + simplifications)
/profile            → Profile (user settings)
/admin              → AdminDashboard (platform stats) — admin only
/admin/users        → UserManagement — admin only
/admin/analyses     → AnalysisManagement — admin only
```

The `Layout` component wraps all authenticated routes with the sidebar navigation. Admin routes are guarded by the `AdminRoute` component which checks `user.role === 'admin'`.

### 2.3 Sidebar Navigation (Sidebar.tsx)

The sidebar is a fixed 240px-wide panel on the left side of the screen. It is divided into sections:

**Workspace group:**
- Dashboard (LayoutDashboard icon)
- New Analysis (PlusCircle icon)
- Compare Texts (ArrowLeftRight icon)
- Batch Analysis (FolderUp icon)
- History (Clock icon)

**Library group:**
- Upload Textbooks (Upload icon)
- Query Textbooks (Search icon)

**Administration group** (admin only):
- Admin Dashboard (Shield icon)
- User Management (Users icon)
- All Analyses (FileText icon)

**Footer:**
- User profile card (avatar, name, role badge)
- Profile settings link
- Dark mode toggle (Moon/Sun icons)
- Log out button

The active route is highlighted with a raised card background and bold text. Hover effects include a subtle rightward translation.

#### Dark Mode

Dark mode is implemented using Tailwind's `darkMode: 'class'` strategy:

1. The toggle in the sidebar adds/removes the `dark` class on `<html>` and sets a `data-theme="dark"` attribute
2. Theme preference is persisted in `localStorage('theme')`
3. On page load, an inline `<script>` in `index.html` reads the preference and applies the class before React renders (prevents flash of wrong theme)
4. CSS custom properties in `index.css` define colour tokens that switch based on `[data-theme="dark"]`

### 2.4 TextInput Component (TextInput.tsx — 662 lines)

The primary entry point for text analysis. Five input methods in a tabbed interface:

#### Tab 1: Text (Direct Paste/Type)
- Large textarea with placeholder "Paste or type your text here…"
- Live word count displayed prominently in a card with the count in 30px display font
- Validity state badge:
  - "Enter text to begin" (neutral) — when empty
  - "X more words needed" (yellow warning) — when under 50 words
  - "Exceeds 50,000 word limit" (red error) — when over limit
  - "Ready for analysis" (green) — valid range
- Character count in bottom-right corner

#### Tab 2: PDF Upload
- Click-to-upload drop zone accepting `.pdf` files (up to 10 MB)
- Calls `textApi.extractPdf(file)` → backend → ML service pdfplumber extraction
- Shows extraction warnings (quality issues from PDF font problems)
- Extracted text appears in an editable textarea below

#### Tab 3: DOC/DOCX Upload
- Same drop zone pattern, accepting `.doc,.docx`
- Calls `textApi.extractDoc(file)` → backend → ML service python-docx extraction
- Success message confirms extraction

#### Tab 4: Image (OCR)
- Accepts `.jpg,.jpeg,.png`
- Calls `textApi.extractImage(file)` → backend → ML service pytesseract OCR
- Shows OCR confidence percentage

#### Tab 5: Voice
- Uses the browser's **Web Speech API** (`webkitSpeechRecognition` / `SpeechRecognition`)
- Large circular microphone button that pulses red when recording
- `recognition.continuous = true` — records continuously until stopped
- `recognition.interimResults = true` — shows in-progress transcription
- Transcribed text appears in an editable textarea
- Fallback message for browsers that don't support the API

#### Sample Texts ("Try a calibrated sample")

Below the text tab, there are **11 calibrated sample texts** (Grade 3 through College), organised into four categories:

| Category | Grades | Button Colour |
|----------|--------|---------------|
| Elementary | 3, 4, 5 | Green |
| Middle School | 6, 7, 8 | Yellow |
| High School | 9, 10, 11, 12 | Orange/Red |
| College | College | Purple |

Each sample has:
- A **title** (e.g., "Tom and Max", "The Water Cycle", "Markets and Economics")
- A **reason** explaining why the text is at that grade level (e.g., "Short sentences averaging 8-10 words. All common 1-2 syllable words. Simple subject-verb sentence patterns.")
- The full **text** (~200-400 words, carefully authored to hit the target grade level within the model's tolerance)

When a sample is selected, the text fills the textarea, the title auto-populates, and a blue info box appears showing the grade-level reasoning. These samples were used to validate the ML model (all 11 pass `validate_test_files.py` with graduated tolerance).

#### Analysis Button

The "Analyze Text" button calls `analysisApi.analyze(text, title)`, which:
1. Sends the text to the backend `POST /api/analyses`
2. Backend proxies to ML service `POST http://localhost:5001/analyze`
3. ML service extracts 16 features, runs 3-model ensemble, detects difficult words/sentences
4. Result saved to PostgreSQL, response returned
5. Frontend navigates to `/analysis/:id` with the full result

A fullscreen `LoadingSpinner` overlay appears during processing with the message "Analyzing text..."

### 2.5 Dashboard (Dashboard.tsx — 394 lines)

The landing page after login. Four sections:

#### 1. Metric Strip (4 Cards)
- **Total Analyses**: count with "N in recent activity" subtitle
- **Average Flesch**: score with "Easy/Moderate/Difficult" label
- **Average Grade**: numeric with "US grade level" subtitle
- **Words Analyzed**: total word count across all analyses (teal-tinted card)

Each card uses the `MetricCard` component with display-font numbers (28px, weight 800), icon in top-right, and subtitle below.

#### 2. Action Row
- **Primary CTA**: Large gradient card linking to `/analyze` — "Start a New Analysis" with "Launch Tool" button
- **AI Observation**: Teal-tinted card with a contextual insight based on the user's corpus. If 3+ analyses: personalised observation about their average grade level. Otherwise: "Analyze a few texts to unlock pattern-based observations."

#### 3. Readability Trend Chart
Shows when 2+ analyses exist. Dual-axis Recharts `LineChart`:
- **Left Y-axis**: Grade Level (0-14) — purple line
- **Right Y-axis**: Flesch Score (0-100) — teal line
- **X-axis**: Date labels from last 20 analyses
- Data fetched via `analysisApi.getAnalyses({ limit: 20 })`, reversed to chronological order

#### 4. Recent Analyses Table
Shows the 3 most recent analyses in a table with:
- Title (clickable link to full analysis)
- Grade level badge
- Date

### 2.6 SimplifyPage (Rewrite Workbench — 1,751 lines)

The most complex frontend component. Accessed via `/simplify/:analysisId`.

#### Controls
- **Target Grade**: Dropdown from Grade 3 to College (13)
- **Mode Toggle**: "Auto" (system applies all changes) or "Interactive" (user accepts/denies each change)
- **Rewrite Button**: Triggers `simplifyApi.analyze()` with the text, target grade, and mode
- **Save Button**: Saves the rewritten text and creates a new analysis from it
- **Export**: PDF and DOCX export buttons

#### Split View
Two side-by-side panels:
- **Left (red-tinted)**: Original text, read-only
- **Right (green-tinted)**: Rewritten text with inline highlighting

#### Grade Preview Bar
Shows "Grade X → Grade Y" with colour-coded badges:
- Original grade (red badge)
- Arrow
- Predicted grade of rewritten text (green badge)
- Target grade in parentheses
- Raw numeric score from the ML model

The predicted grade is computed by calling `analysisApi.preview(simplifiedText)` — a lightweight analysis endpoint that returns predictions without saving to the database. This is debounced (200ms) and runs whenever the simplified text changes.

#### Change Highlighting (HighlightedText Component)

The rewritten text panel uses a sophisticated multi-layer highlighting system:

**Three levels of highlights:**

1. **Word-level highlights** (individual word replacements):
   - Pending: amber background with amber underline
   - Accepted: green background
   - Hovered: intensified colour (amber-400 or green-400)

2. **Sentence/Paragraph-level highlights** (structural changes):
   - Blue background for sentence/paragraph rewrites
   - Blue intensifies on hover

3. **Embedded evidence highlights** (within sentence-level highlights):
   - Teal underline showing specific word changes within a broader structural change
   - Evidence items from `explanation_items` are located in the text and marked

**How highlighting works internally:**

The `buildPreviewState()` function computes the preview text by applying accepted changes to the original text:
1. Sort changes by `start` position
2. Walk through the original text, inserting replacement text at each change's span
3. Track the new positions (`ranges`) of each change in the preview text

In interactive mode, pending changes show inline ✓/✗ buttons next to each highlighted word. Accepting or denying a change rebuilds the preview text.

#### Paragraph Reviews (Auto Mode)

In auto mode, the component builds `ParagraphReview` objects that explain what happened to each paragraph:
- Splits original and rewritten text into paragraph chunks
- Computes sentence count, word count, and clause count before/after
- Collects evidence items (word replacements with before/after, Zipf frequencies, syllable counts)
- Generates a natural-language reason string: "Reworked this paragraph for Grade 6: split dense syntax into 4 clearer sentences, reduced complex clause load from 8 to 5 estimated clause units..."

These appear as green-bordered cards below the text panels.

#### Hover Tooltip

When hovering over any highlight, a floating tooltip appears showing:
- Change type badge (Word Replacement, Sentence Split, Paragraph Rewrite, etc.)
- Scope badge (Word Review, Sentence Review, Paragraph Review)
- Reason text explaining why the change was made
- Evidence items with before→after word pairs, Zipf frequencies, and syllable counts
- In interactive mode: Accept/Deny buttons within the tooltip

#### Save Flow

When the user clicks "Save":
1. In interactive mode: calls `simplifyApi.apply()` with accepted change IDs to get the final text
2. Saves to `simplification_history` table via `simplifyApi.save()`
3. Creates a **new analysis** from the rewritten text via `analysisApi.analyze()` with title "Rewritten to Grade X"
4. Navigates to the new analysis result page — the user immediately sees how the ML model scores the rewritten version

### 2.7 Frontend-Only Analysis Features

These features run entirely in the browser with no backend calls. They use the existing analysis data returned by the API.

#### Complexity Score (0-100)
**File:** `frontend/src/utils/complexityScore.ts` (135 lines)

A single composite number that captures overall text difficulty:

```
complexity = (grade/13) × 40           // Grade level contributes 40%
           + ((100-flesch)/100) × 30   // Flesch contributes 30% (inverted)
           + (diffWords%/100) × 20     // Difficult words contribute 20%
           + min(sentLen/30, 1) × 10   // Sentence length contributes 10%
```

Displayed as an animated gauge in the `ComplexityScoreCard` component with colour-coded interpretation (green for low complexity, red for high).

#### Reading Time Estimate
**File:** `frontend/src/utils/readingTime.ts` (112 lines)

Adjusts the standard 225 WPM reading speed based on text difficulty:

```
multiplier = 0.6 + (fleschScore / 100) × 0.4
// Flesch 0 (very hard): 0.6 × 225 = 135 WPM
// Flesch 50 (moderate): 0.8 × 225 = 180 WPM
// Flesch 100 (very easy): 1.0 × 225 = 225 WPM

readingTime = wordCount / (225 × multiplier)
```

Displayed as the 5th summary card in the analysis results header alongside word count, sentence count, average sentence length, and average syllables.

#### Improvement Suggestions
**File:** `frontend/src/utils/improvementSuggestions.ts` (200 lines)

Generates 3-5 prioritised actionable suggestions based on the analysis metrics:

- **High priority** (red): Issues that most impact grade level (e.g., "Reduce average sentence length from 28 to under 20 words — could lower grade by ~1.5 levels")
- **Medium priority** (yellow): Moderate improvements (e.g., "Replace 15% of difficult vocabulary with simpler alternatives")
- **Low priority** (green): Fine-tuning suggestions (e.g., "Consider varying sentence length for better pacing")

Each suggestion includes an estimated grade-level impact. Displayed in the `ImprovementSuggestions` component below the charts.

#### Vocabulary Level Analysis
**File:** `frontend/src/utils/vocabularyAnalysis.ts` (217 lines)

Categorises all words into four levels:
- **Simple**: Common everyday words (not flagged as difficult)
- **Medium**: Words with 3+ syllables that aren't in the difficult words list
- **Advanced**: Words flagged as difficult by the analysis
- **Expert**: A subset of difficult words with very low frequency

Displayed as a stacked horizontal bar chart in the `VocabularyAnalysis` component showing the percentage distribution.

#### Detailed PDF Report
**File:** `frontend/src/utils/detailedReport.ts`

Multi-page jsPDF report generated entirely client-side:
- **Page 1: Cover** — Title, grade level banner, date, complexity score
- **Page 2: Scores Table** — All readability scores with interpretation strings
- **Page 3: Complexity Breakdown** — Weighted components table (grade 40%, Flesch 30%, difficult words 20%, sentence length 10%)
- **Page 4: Improvement Suggestions** — Priority-coloured bullet points with estimated grade impact
- **Page 5: Vocabulary Analysis** — Word level distribution
- **Pages 6+: Difficult Passages** — Up to 30 difficult words with full reasons (no truncation), up to 8 difficult sentences with metadata

---

## 3. Authentication System

### 3.1 How Authentication Works

ClarityWorks uses **JSON Web Tokens (JWT)** for stateless authentication. The flow:

```
User enters email + password
        │
        ▼
POST /api/auth/login
        │
        ▼
Backend checks:
  1. User exists in PostgreSQL users table
  2. bcrypt.compare(password, password_hash) — 10 rounds
  3. Account is active (is_active = true)
        │
        ▼
Generate JWT with:
  - userId, email, role
  - 24-hour expiry
  - Signed with JWT_SECRET
        │
        ▼
Return { token, user }
        │
        ▼
Frontend stores in localStorage:
  - 'token' → JWT string
  - 'user' → JSON serialised user object
        │
        ▼
All subsequent API calls:
  Authorization: Bearer <token>
```

### 3.2 Frontend Auth System (`auth.tsx`)

The `AuthProvider` component wraps the entire application and provides auth state via React Context:

```typescript
interface AuthContextType {
  user: User | null;      // Current user object
  token: string | null;   // JWT token
  isLoading: boolean;     // True during initial hydration
  login: (email, password) => Promise<void>;
  register: (email, password, fullName) => Promise<void>;
  logout: () => void;
  refreshUser: () => void;
}
```

**On app startup:**
1. `AuthProvider` reads `token` and `user` from `localStorage`
2. If found, sets them in React state (user is already authenticated)
3. Sets `isLoading = false`

**On login:** Calls `authApi.login()`, stores token + user in localStorage and state.

**On logout:** Clears localStorage and state. User is redirected to `/login`.

**The `useAuth()` hook** exposes the auth context to any component. Used throughout the app to:
- Display user name/avatar in the sidebar
- Check admin role for route guarding
- Attach JWT to API requests

### 3.3 Axios JWT Interceptor (`api.ts`)

Every API request automatically includes the JWT token:

```typescript
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

**Response interceptor** handles expired/invalid tokens:
```typescript
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Don't redirect for login/register attempts (401 = wrong credentials)
    const isAuthRoute = error.config?.url?.includes('/api/auth/login') ||
                        error.config?.url?.includes('/api/auth/register');

    if (error.response?.status === 401 && !isAuthRoute) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';   // Force redirect
    }
    return Promise.reject(error);
  }
);
```

This means: if any protected API call returns 401 (token expired or invalid), the user is automatically logged out and redirected to login. But if a login or register attempt returns 401, it's just wrong credentials — don't redirect.

### 3.4 Backend Auth Middleware (`auth.ts`)

Two middleware functions protect backend routes:

**`authMiddleware`** — Verifies JWT on every protected route:
1. Extract `Bearer <token>` from `Authorization` header
2. Call `jwt.verify(token, JWT_SECRET)` — throws if expired or invalid
3. Decode payload to get `userId`, `email`, `role`
4. Attach to `req` object as `req.userId`, `req.userEmail`, `req.userRole`
5. Call `next()` — request proceeds to the controller

**`adminMiddleware`** — Additional check for admin-only routes:
- Checks `req.userRole !== 'admin'`
- Returns 403 Forbidden if not admin
- Used on all `/api/admin/*` routes

### 3.5 Password Requirements

Enforced by `passwordValidator.ts` on the backend and `PasswordStrength.tsx` on the frontend:

- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character

The frontend shows a real-time password strength indicator during registration with checkmarks for each requirement.

---

## 4. Database Schema (PostgreSQL)

### 4.1 Schema Initialisation

The database schema is defined in `backend/src/config/database.ts`. Tables are **auto-created on backend startup** via `initDatabase()` — no manual migration needed.

The function uses `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` patterns, so it's safe to run repeatedly. Existing data is never dropped.

### 4.2 Connection Pool

```typescript
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 20,                    // Max 20 concurrent connections
  idleTimeoutMillis: 30000,   // Close idle connections after 30s
  connectionTimeoutMillis: 2000,  // Timeout connecting after 2s
});
```

### 4.3 Table Definitions

#### `users` Table

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | Auto-increment |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Login identifier |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt hash (10 rounds) |
| full_name | VARCHAR(255) | NOT NULL | Display name |
| role | VARCHAR(20) | DEFAULT 'user' | 'user' or 'admin' |
| is_active | BOOLEAN | DEFAULT true | Soft-delete / disable |
| profile_picture | VARCHAR(500) | nullable | File path |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Auto-set |

#### `analyses` Table

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | Auto-increment |
| user_id | INTEGER | FK → users(id) ON DELETE CASCADE | Owner |
| original_text | TEXT | NOT NULL | Full input text |
| title | VARCHAR(255) | nullable | User-set or auto-generated |
| word_count | INTEGER | | Basic metric |
| sentence_count | INTEGER | | Basic metric |
| avg_sentence_length | DECIMAL | | Words per sentence |
| avg_syllables_per_word | DECIMAL | | Syllables average |
| flesch_reading_ease | DECIMAL | | 0-100 scale |
| flesch_kincaid_grade | DECIMAL | | US grade level |
| automated_readability_index | DECIMAL | | ARI score |
| smog_readability | DECIMAL | | SMOG index |
| coleman_liau_index | DECIMAL | | Coleman-Liau score |
| predicted_grade_level | VARCHAR(50) | | "Grade 3" through "College" |
| predicted_complexity | VARCHAR(50) | | Beginner/Intermediate/Advanced/Expert |
| confidence | DECIMAL | | 0.5-0.99 |
| difficult_words_count | INTEGER | | Count |
| difficult_words_percentage | DECIMAL | | Percentage |
| difficult_words | JSONB | | Array of {word, position, syllables, reason} |
| difficult_sentences | JSONB | | Array of {sentence, position, word_count, reason, flesch_score} |
| concept_graph | JSONB | nullable | {concepts: [], edges: []} |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Auto-set |

**Indexes:** `idx_analyses_user_id`, `idx_analyses_created_at` (DESC)

**Why JSONB for difficult_words and difficult_sentences?** These are variable-length arrays of complex objects. A normalised relational design would need join tables with many-to-many relationships. JSONB stores them as flexible nested data within a single column, making reads fast (one query instead of joins) and writes simple (insert the whole analysis in one go). PostgreSQL supports JSONB indexing and querying if needed.

#### `simplification_history` Table

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | Auto-increment |
| analysis_id | INTEGER | FK → analyses(id) CASCADE | Linked analysis |
| user_id | INTEGER | FK → users(id) CASCADE | Owner |
| original_text | TEXT | NOT NULL | Original text |
| simplified_text | TEXT | NOT NULL | Rewritten version |
| target_grade | VARCHAR(50) | NOT NULL | Target grade level |
| changes_applied | JSONB | NOT NULL | Array of applied changes |
| mode | VARCHAR(20) | CHECK ('auto','interactive') | Rewrite mode used |
| metrics_original | JSONB | nullable | Pre-rewrite metrics |
| metrics_simplified | JSONB | nullable | Post-rewrite metrics |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Auto-set |

**Indexes:** `idx_simplification_user`, `idx_simplification_analysis`

#### `rag_documents` Table

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | Auto-increment |
| user_id | INTEGER | FK → users(id) CASCADE | Owner |
| filename | VARCHAR(255) | NOT NULL | Stored filename |
| original_filename | VARCHAR(255) | NOT NULL | Original upload name |
| file_size_bytes | INTEGER | | File size |
| total_pages | INTEGER | | Page count |
| total_chunks | INTEGER | | Number of chunks created |
| chromadb_collection_id | VARCHAR(255) | UNIQUE, NOT NULL | ChromaDB collection reference |
| concept_graph | JSONB | nullable | {concepts: [], edges: []} |
| uploaded_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Auto-set |

**Index:** `idx_rag_docs_user`

#### `rag_queries` Table

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | SERIAL | PRIMARY KEY | Auto-increment |
| user_id | INTEGER | FK → users(id) CASCADE | Owner |
| query_text | TEXT | NOT NULL | User's question |
| document_ids | TEXT[] | | Array of queried document collection IDs |
| result_count | INTEGER | | Number of results returned |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Auto-set |

**Index:** `idx_rag_queries_user`

### 4.4 Cascade Deletes

All foreign keys use `ON DELETE CASCADE`. Deleting a user automatically deletes all their:
- Analyses (and their concept graphs)
- Simplification history records
- RAG documents (and their ChromaDB collections are deleted separately via the ragController)
- RAG query records

---

## 5. Complete Data Flow Diagrams

### 5.1 Text Analysis Flow

```
User types/pastes text  →  TextInput.tsx validates (≥50 words)
        │
        ▼
analysisApi.analyze(text, title)  →  POST /api/analyses
        │
        ▼
auth.ts middleware verifies JWT  →  extracts userId
        │
        ▼
analysisController.ts validates text (50-50,000 chars)
        │
        ▼
axios.post('http://localhost:5001/analyze', { text })
        │
        ▼
Flask app.py /analyze endpoint:
  1. TextProcessor → basic metrics (word count, syllables, sentences)
  2. FeatureExtractor → 16 ML features + 8 readability scores
  3. ReadabilityModel → 3-model ensemble prediction + confidence
  4. TextProcessor → difficult words + difficult sentences
        │
        ▼
Return to backend:
  {basic_metrics, readability_scores, predictions,
   difficult_elements, statistics}
        │
        ▼
analysisController saves to PostgreSQL analyses table
  (INSERT with all metrics + JSONB arrays)
        │
        ▼
Return {success, analysisId, analysis} to frontend
        │
        ▼
navigate(`/analysis/${analysisId}`)  →  AnalysisResults.tsx
  - Summary cards (word count, sentences, avg length, syllables, reading time)
  - Grade explanation with layman/technical toggle
  - Complexity score gauge (0-100)
  - Charts (radar, bar, pie, gauge, common words)
  - Highlighted text with difficult word/sentence markers
  - Improvement suggestions
  - Vocabulary level analysis
  - Concept graph (generate on demand)
  - Export buttons (PDF, Detailed Report)
  - "Simplify Text" button → navigates to SimplifyPage
```

### 5.2 Text Rewrite Flow

```
User clicks "Simplify Text" → /simplify/:analysisId
        │
        ▼
SimplifyPage loads original text + grade via analysisApi.getAnalysis()
        │
        ▼
User selects target grade + mode (auto/interactive)
        │
        ▼
simplifyApi.analyze({analysisId, targetGrade, mode})
  → POST /api/simplify/analyze → POST http://localhost:5001/simplify/analyze
        │
        ▼
simplifier.py TextSimplifier.simplify_to_grade():
  1. Detect direction (upgrade vs downgrade)
  2. Select policy bucket
  3. Generate BEAM_WIDTH=3 candidates:
     a. Rule-based candidate (word replacements + sentence splits/combines)
     b. LLM candidates (Fireworks AI Llama 3.3 70B)
  4. Score each candidate (~15 weighted dimensions)
  5. Select best candidate
  6. Validate and optionally run correction pass
  7. Extract word-level diff changes
        │
        ▼
Return {original_text, suggested_changes[], preview_text,
        preview_metrics, selection_summary}
        │
        ▼
SimplifyPage renders:
  - Split view (original vs rewritten with highlights)
  - Grade preview bar (Grade X → Grade Y)
  - Change list with evidence items
  - Paragraph review cards (auto mode)
        │
        ▼
User clicks "Save":
  1. simplifyApi.save() → saves to simplification_history table
  2. analysisApi.analyze(rewrittenText) → creates new analysis
  3. navigate to new analysis result page
```

### 5.3 RAG Query Flow

```
User uploads PDF/DOCX → RAGUpload.tsx
        │
        ▼
ragApi.uploadDocument(file)
  → POST /api/rag/upload → POST http://localhost:5001/rag/upload
        │
        ▼
rag_engine.py upload_document():
  1. pdfplumber / python-docx extracts text
  2. RecursiveCharacterTextSplitter → 1500-char chunks, 300 overlap
  3. E5-small-v2 embeds each chunk (384 dims, "passage: " prefix)
  4. Stored in ChromaDB collection (doc_{uuid})
        │
        ▼
Backend saves metadata to rag_documents table
        │
        ▼
User types question → RAGQuery.tsx
        │
        ▼
ragApi.queryDocuments(query, documentIds)
  → POST /api/rag/query → POST http://localhost:5001/rag/query
        │
        ▼
rag_engine.py query_documents():
  Stage 1: Embed query ("query: " prefix), top-20 from ChromaDB
  Stage 2: Keyword scoring + hybrid merge (semantic 70% + keyword 30%)
  Stage 3: FlashRank cross-encoder re-ranks to top-5
  Stage 4: Fireworks AI generates answer with [Source N] citations
        │
        ▼
Return {answer, sources[], has_answer}
        │
        ▼
RAGQuery.tsx displays:
  - Answer in insight box with Bot icon
  - Expandable source documents with match scores
  - Export (PDF/DOCX)
```

---

## 6. TypeScript Type System

All TypeScript interfaces are defined in `frontend/src/types/index.ts` (335 lines). Key interfaces:

### Core Types

```typescript
interface User {
  id: number;
  email: string;
  fullName: string;
  role: 'user' | 'admin';
  isActive: boolean;
  profilePicture?: string;
  createdAt: string;
}

interface Analysis {
  basic_metrics: BasicMetrics;      // word_count, sentence_count, etc.
  readability_scores: ReadabilityScores;  // flesch, ARI, SMOG, etc.
  predictions: Predictions;         // grade_level, complexity, confidence
  difficult_elements: DifficultElements;  // words + sentences
  statistics: Statistics;           // counts and percentages
}

interface ConceptGraph {
  concepts: ConceptNode[];   // {id, label, tier, description}
  edges: ConceptEdge[];      // {from, to, relationship}
}
```

### Simplification Types

```typescript
interface SimplificationChange {
  type: string;              // 'word_replacement', 'sentence_split', etc.
  original: string;
  simplified: string;
  reason: string;
  id: number;
  start: number;             // Position in original text
  end: number;
  review_scope?: 'word' | 'sentence' | 'paragraph';
  explanation_items?: SimplificationExplanationItem[];
  dependency_group_id?: string;  // Groups linked structural changes
  final_reviewed?: boolean;      // Changed by final review pass
  // ... many more fields for scoring, validation, evidence
}

interface SimplificationSelectionSummary {
  policy_bucket: string;
  beam_width: number;
  source_grade: number;
  target_grade: number;
  selected_score: number;
  top_candidates: SimplificationSelectionCandidate[];
  // ... comprehensive beam search diagnostics
}
```

---

## 7. Running the Complete System

### Prerequisites
- **Node.js** v18+
- **Python** 3.9+
- **PostgreSQL** 14+
- **Tesseract OCR** (for image text extraction — optional)

### Database Setup

```sql
CREATE DATABASE clarityworks_db;
CREATE USER clarityworks_user WITH PASSWORD 'clarityworks_pass';
GRANT ALL PRIVILEGES ON DATABASE clarityworks_db TO clarityworks_user;
\c clarityworks_db
GRANT ALL ON SCHEMA public TO clarityworks_user;
```

Tables are auto-created on backend startup.

### Starting All Three Services

```bash
# Terminal 1 — Backend (Port 5000)
cd backend
npm install
npm run dev

# Terminal 2 — ML Service (Port 5001)
cd ml-service
venv\Scripts\activate    # Windows
python app.py

# Terminal 3 — Frontend (Port 5173)
cd frontend
npm install
npm run dev
```

Access the application at **http://localhost:5173**.

### Environment Variables

**Backend** (`backend/.env`):
```
PORT=5000
DATABASE_URL=postgresql://clarityworks_user:clarityworks_pass@localhost:5432/clarityworks_db
JWT_SECRET=your_super_secret_jwt_key_change_this_in_production
PYTHON_SERVICE_URL=http://localhost:5001
NODE_ENV=development
```

**Frontend** (`frontend/.env`):
```
VITE_API_URL=http://localhost:5000
VITE_PYTHON_API_URL=http://localhost:5001
```

**ML Service** (`ml-service/.env`):
```
FLASK_PORT=5001
FLASK_ENV=production
TESSERACT_PATH=C:/Program Files/Tesseract-OCR/tesseract.exe
FIREWORKS_API_KEY=...   # Required for text rewriting, RAG answers, concept graphs
```

### Training the ML Model (Optional)

```bash
cd ml-service
python train_model.py
```

The app works without trained models — it falls back to a Flesch-Kincaid grade heuristic. But trained models provide much better accuracy (MAE 0.712 vs ~2.0 with the heuristic).

### Known Issue: torch DLL on Windows

The `thinc` library (spaCy dependency) tries to import `torch`, which may fail with a DLL error on Windows. Fix: `models/__init__.py` sets `os.environ['THINC_NO_TORCH'] = '1'` before importing spaCy. If this doesn't work, patch `venv/Lib/site-packages/thinc/compat.py` to change `except ImportError:` to `except (ImportError, OSError):` in the torch import block.

---

## 8. Key Libraries Summary (All Services)

### Frontend Libraries

| Library | Role |
|---------|------|
| React 18 | Component-based UI |
| TypeScript 5.2 | Static typing |
| Vite 5.0 | Dev server + build |
| TailwindCSS 3.3 | Utility CSS |
| Recharts 2.10 | Charts (line, radar, bar, pie, gauge) |
| ReactFlow | Interactive graph rendering |
| dagre | Graph auto-layout |
| Axios 1.6 | HTTP client + JWT interceptor |
| React Router 6.21 | Client-side routing |
| react-hook-form 7.49 | Form management |
| lucide-react 0.294 | Icons |
| jsPDF 2.5 | PDF generation |
| jspdf-autotable 3.8 | PDF tables |
| docx 8.5 | DOCX generation |
| file-saver 2.0 | File downloads |

### Backend Libraries

| Library | Role |
|---------|------|
| Express 4.18 | Web framework |
| pg 8.11 | PostgreSQL driver |
| bcrypt 5.1 | Password hashing (10 rounds) |
| jsonwebtoken 9.0 | JWT generation/verification |
| multer 1.4 | File uploads (two configs: 5MB profiles, 100MB documents) |
| axios 1.6 | HTTP client to ML service |
| form-data | File forwarding to ML service |
| express-validator 7.0 | Input validation |

### ML Service Libraries

| Library | Role |
|---------|------|
| Flask 3.0 | Web framework |
| scikit-learn 1.3.2 | Random Forest, Gradient Boosting, GridSearchCV |
| XGBoost 2.0.3 | Third ensemble model |
| spaCy 3.7.2 + en_core_web_sm | NLP features, dependency parsing, sentence splitting |
| NLTK 3.9.1 | WordNet synonym finding |
| wordfreq 3.1.1 | Zipf word frequency |
| textstat 0.7.3 | 8 readability formulas |
| pyphen 0.14 | Syllable counting |
| ChromaDB 0.4.22 | Vector database |
| sentence-transformers 2.3.1 | E5-small-v2 embeddings |
| FlashRank 0.2+ | Cross-encoder re-ranking |
| langchain-text-splitters 0.2+ | Recursive text chunking |
| pdfplumber 0.10.3 | PDF extraction |
| python-docx 1.1 | DOCX extraction |
| pytesseract 0.3.10 | OCR |
| OpenAI SDK | Fireworks AI client (concept extraction, rewriting, RAG answers) |

---

## 9. External API: Fireworks AI

ClarityWorks uses **Fireworks AI** as its LLM provider. The OpenAI Python SDK is pointed at Fireworks' API:

```python
client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=os.getenv('FIREWORKS_API_KEY'),
)
```

**Model:** `accounts/fireworks/models/llama-v3p3-70b-instruct` (Llama 3.3 70B Instruct)

**Used for:**
1. **Text rewriting** — beam search candidate generation, target lock repair, final review
2. **RAG answer generation** — synthesising answers from retrieved document chunks
3. **Concept graph extraction** — generating concept/edge JSON from text + noun phrases
4. **Simplification validation** — verifying rule-based changes preserve meaning

**Why Fireworks AI?** It provides an OpenAI-compatible API (same SDK, same request format) hosting open-weight models like Llama 3.3 70B. This avoids vendor lock-in to OpenAI while providing access to a capable 70B-parameter model with fast inference.

**No external API is needed for the core ML prediction pipeline.** All three ensemble models (RF, GB, XGBoost) run locally on CPU. The Fireworks API is only used for generative tasks (rewriting, answering, concept extraction).
