# ClarityWorks - Software Requirements and Design Specification (SRDS)

## Table of Contents
1. [Project Overview](#project-overview)
2. [File Structure](#file-structure)
3. [Database Schema (ERD)](#database-schema-erd)
4. [Class Diagrams](#class-diagrams)

---

## Project Overview

**ClarityWorks** is a full-stack text readability analysis application that uses machine learning to predict reading grade levels and identify difficult text elements.

### Technology Stack
| Layer | Technologies |
|-------|-------------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Recharts |
| Backend | Node.js, Express, TypeScript, PostgreSQL |
| ML Service | Python, Flask, scikit-learn, textstat |

---

## File Structure

```
clarityworksv2/
│
├── backend/                          # Express.js Backend API
│   ├── src/
│   │   ├── config/
│   │   │   └── database.ts           # PostgreSQL connection pool & schema initialization
│   │   │
│   │   ├── controllers/
│   │   │   ├── authController.ts     # User authentication (register, login, logout, getMe)
│   │   │   ├── analysisController.ts # Text analysis CRUD operations & statistics
│   │   │   ├── textController.ts     # File extraction (PDF, DOC, Image/OCR)
│   │   │   └── adminController.ts    # Admin panel operations (user/analysis management)
│   │   │
│   │   ├── middleware/
│   │   │   └── auth.ts               # JWT authentication & admin authorization middleware
│   │   │
│   │   ├── routes/
│   │   │   ├── authRoutes.ts         # Authentication endpoints (/api/auth/*)
│   │   │   ├── analysisRoutes.ts     # Analysis endpoints (/api/analyses/*)
│   │   │   ├── textRoutes.ts         # Text extraction endpoints (/api/text/*)
│   │   │   └── adminRoutes.ts        # Admin endpoints (/api/admin/*)
│   │   │
│   │   ├── models/                   # (Empty - uses direct SQL queries)
│   │   ├── utils/
│   │   │   └── passwordValidator.ts  # Password complexity validation utility
│   │   │
│   │   └── server.ts                 # Express app initialization & server startup
│   │
│   ├── uploads/                      # Temporary file uploads directory
│   ├── package.json                  # Node.js dependencies
│   ├── tsconfig.json                 # TypeScript configuration
│   └── .env                          # Environment variables (PORT, DATABASE_URL, JWT_SECRET)
│
├── frontend/                         # React Frontend Application
│   ├── src/
│   │   ├── components/
│   │   │   ├── Admin/
│   │   │   │   ├── AdminDashboard.tsx    # Admin dashboard with platform statistics
│   │   │   │   ├── AdminRoute.tsx        # Protected route wrapper for admin pages
│   │   │   │   ├── AnalysisManagement.tsx # Admin analysis management table
│   │   │   │   └── UserManagement.tsx    # Admin user management with CRUD operations
│   │   │   │
│   │   │   ├── Analysis/
│   │   │   │   ├── AnalysisResults.tsx   # Full analysis results display with charts & PDF export
│   │   │   │   ├── Charts.tsx            # Recharts components (Radar, Bar, Pie, Gauge)
│   │   │   │   └── HighlightedText.tsx   # Interactive text with difficulty highlighting
│   │   │   │
│   │   │   ├── Auth/
│   │   │   │   ├── Login.tsx             # Login form with validation
│   │   │   │   ├── PasswordStrength.tsx  # Password strength indicator component
│   │   │   │   └── Register.tsx          # Registration form with password strength validation
│   │   │   │
│   │   │   ├── Dashboard/
│   │   │   │   └── Dashboard.tsx         # User dashboard with stats & recent analyses
│   │   │   │
│   │   │   ├── History/
│   │   │   │   └── History.tsx           # Analysis history with search, filter, pagination
│   │   │   │
│   │   │   ├── Layout/
│   │   │   │   ├── Layout.tsx            # Main layout wrapper with sidebar
│   │   │   │   └── Sidebar.tsx           # Navigation sidebar component
│   │   │   │
│   │   │   └── TextInput/
│   │   │       └── TextInput.tsx         # Multi-method input (text, PDF, DOC, image, voice)
│   │   │
│   │   ├── pages/                    # (Empty - uses components directly)
│   │   │
│   │   ├── services/
│   │   │   └── api.ts                # Axios API client with auth interceptors
│   │   │
│   │   ├── types/
│   │   │   └── index.ts              # TypeScript interfaces for all data types
│   │   │
│   │   ├── utils/
│   │   │   ├── auth.tsx              # AuthContext provider & useAuth hook
│   │   │   └── exportPdf.ts          # PDF export utility using jsPDF
│   │   │
│   │   ├── App.tsx                   # React Router configuration
│   │   ├── main.tsx                  # React entry point
│   │   └── index.css                 # Tailwind CSS imports
│   │
│   ├── public/                       # Static assets
│   ├── package.json                  # React dependencies
│   ├── tailwind.config.js            # Tailwind CSS configuration
│   ├── vite.config.ts                # Vite build configuration with API proxy
│   └── tsconfig.json                 # TypeScript configuration
│
└── ml-service/                       # Python ML Service
    ├── models/
    │   ├── __init__.py               # Package initialization
    │   ├── text_processor.py         # Text processing, syllable counting, word analysis
    │   ├── feature_extractor.py      # ML feature extraction (11 features)
    │   └── readability_model.py      # Ensemble ML models (Random Forest + Gradient Boosting)
    │
    ├── trained_models/               # Serialized joblib model files
    │   ├── rf_model.joblib           # Trained Random Forest model
    │   └── gb_model.joblib           # Trained Gradient Boosting model
    │
    ├── data/
    │   └── clear_corpus/             # CLEAR Corpus training dataset
    │
    ├── utils/
    │   └── __init__.py               # Utility functions
    │
    ├── app.py                        # Flask API server with endpoints
    ├── train_model.py                # Model training script
    ├── requirements.txt              # Python dependencies
    └── venv/                         # Python virtual environment
```

### File Descriptions Summary

| Directory | Purpose |
|-----------|---------|
| `backend/src/config/` | Database connection and schema setup |
| `backend/src/controllers/` | Request handlers for authentication, analysis, and file extraction |
| `backend/src/middleware/` | JWT authentication middleware |
| `backend/src/routes/` | API route definitions |
| `frontend/src/components/` | React UI components organized by feature |
| `frontend/src/services/` | API client with Axios |
| `frontend/src/types/` | TypeScript type definitions |
| `frontend/src/utils/` | Authentication context and hooks |
| `ml-service/models/` | Python classes for text processing and ML prediction |
| `ml-service/trained_models/` | Serialized ML model files |

---

## Database Schema (ERD)

### Entity Relationship Diagram

```
┌─────────────────────────────────────────┐
│                 USERS                    │
├─────────────────────────────────────────┤
│ PK  id              SERIAL              │
│     email           VARCHAR(255) UNIQUE │
│     password_hash   VARCHAR(255)        │
│     full_name       VARCHAR(255)        │
│     role            VARCHAR(20)         │
│     is_active       BOOLEAN             │
│     profile_picture VARCHAR(500)        │
│     created_at      TIMESTAMP           │
└─────────────────────────────────────────┘
                    │
                    │ 1
                    │
                    │
                    │ *
                    ▼
┌─────────────────────────────────────────┐
│               ANALYSES                   │
├─────────────────────────────────────────┤
│ PK  id                         SERIAL   │
│ FK  user_id                    INTEGER  │──────► users(id) ON DELETE CASCADE
│     original_text              TEXT     │
│     title                      VARCHAR  │
│     word_count                 INTEGER  │
│     sentence_count             INTEGER  │
│     avg_sentence_length        DECIMAL  │
│     avg_syllables_per_word     DECIMAL  │
│     flesch_reading_ease        DECIMAL  │
│     flesch_kincaid_grade       DECIMAL  │
│     automated_readability_index DECIMAL │
│     smog_readability           DECIMAL  │
│     coleman_liau_index         DECIMAL  │
│     predicted_grade_level      VARCHAR  │
│     predicted_complexity       VARCHAR  │
│     confidence                 DECIMAL  │
│     difficult_words_count      INTEGER  │
│     difficult_words_percentage DECIMAL  │
│     difficult_words            JSONB    │
│     difficult_sentences        JSONB    │
│     created_at                 TIMESTAMP│
└─────────────────────────────────────────┘
```

### Table: USERS

| Column | Data Type | Constraints | Description |
|--------|-----------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-incrementing unique identifier |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | User's email address |
| `password_hash` | VARCHAR(255) | NOT NULL | Bcrypt hashed password (10 rounds) |
| `full_name` | VARCHAR(255) | NOT NULL | User's display name |
| `role` | VARCHAR(20) | DEFAULT 'user' | User role ('user' or 'admin') |
| `is_active` | BOOLEAN | DEFAULT true | Account active status |
| `profile_picture` | VARCHAR(500) | | URL or path to user's profile picture |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Account creation date |

### Table: ANALYSES

| Column | Data Type | Constraints | Description |
|--------|-----------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-incrementing unique identifier |
| `user_id` | INTEGER | FOREIGN KEY, NOT NULL | References users(id), CASCADE delete |
| `original_text` | TEXT | NOT NULL | Full input text for analysis |
| `title` | VARCHAR(255) | | Analysis title (auto-generated if null) |
| `word_count` | INTEGER | | Total number of words |
| `sentence_count` | INTEGER | | Total number of sentences |
| `avg_sentence_length` | DECIMAL | | Average words per sentence |
| `avg_syllables_per_word` | DECIMAL | | Average syllables per word |
| `flesch_reading_ease` | DECIMAL | | Flesch Reading Ease score (0-100) |
| `flesch_kincaid_grade` | DECIMAL | | Flesch-Kincaid US grade level |
| `automated_readability_index` | DECIMAL | | ARI score |
| `smog_readability` | DECIMAL | | SMOG index |
| `coleman_liau_index` | DECIMAL | | Coleman-Liau index |
| `predicted_grade_level` | VARCHAR(50) | | ML predicted grade (Grade 3 - College) |
| `predicted_complexity` | VARCHAR(50) | | Complexity category |
| `confidence` | DECIMAL | | ML model confidence (0-1) |
| `difficult_words_count` | INTEGER | | Count of difficult words |
| `difficult_words_percentage` | DECIMAL | | Percentage of difficult words |
| `difficult_words` | JSONB | | Array of difficult word objects |
| `difficult_sentences` | JSONB | | Array of difficult sentence objects |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Analysis creation date |

### JSONB Field Structures

#### difficult_words (JSONB Array)
```json
[
  {
    "word": "string",
    "position": "number",
    "syllables": "number",
    "reason": "string"
  }
]
```

#### difficult_sentences (JSONB Array)
```json
[
  {
    "sentence": "string",
    "position": "number",
    "word_count": "number",
    "reason": "string",
    "flesch_score": "number"
  }
]
```

### Database Indexes

```sql
CREATE INDEX idx_analyses_user_id ON analyses(user_id);
CREATE INDEX idx_analyses_created_at ON analyses(created_at DESC);
```

### Relationships

| Relationship | Type | Description |
|--------------|------|-------------|
| Users -> Analyses | One-to-Many | One user can have many analyses |
| Analyses -> Users | Many-to-One | Each analysis belongs to one user |

**Cascade Rules:**
- When a user is deleted, all their analyses are automatically deleted (ON DELETE CASCADE)

---

## Class Diagrams

### Backend Controllers

```
┌─────────────────────────────────────────────────────────────┐
│                      AuthController                          │
├─────────────────────────────────────────────────────────────┤
│ (No instance attributes - stateless controller)              │
├─────────────────────────────────────────────────────────────┤
│ + register(req: Request, res: Response): Promise<void>       │
│ + login(req: Request, res: Response): Promise<void>          │
│ + getMe(req: AuthRequest, res: Response): Promise<void>      │
│ + logout(req: Request, res: Response): Promise<void>         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    AnalysisController                        │
├─────────────────────────────────────────────────────────────┤
│ (No instance attributes - stateless controller)              │
├─────────────────────────────────────────────────────────────┤
│ + analyzeText(req: AuthRequest, res: Response): Promise<void>│
│ + getAnalyses(req: AuthRequest, res: Response): Promise<void>│
│ + getAnalysisById(req: AuthRequest, res: Response): Promise  │
│ + deleteAnalysis(req: AuthRequest, res: Response): Promise   │
│ + getStats(req: AuthRequest, res: Response): Promise<void>   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      TextController                          │
├─────────────────────────────────────────────────────────────┤
│ + upload: Multer                                             │
├─────────────────────────────────────────────────────────────┤
│ + extractPdf(req: Request, res: Response): Promise<void>     │
│ + extractDoc(req: Request, res: Response): Promise<void>     │
│ + extractImage(req: Request, res: Response): Promise<void>   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      AdminController                         │
├─────────────────────────────────────────────────────────────┤
│ (No instance attributes - stateless controller)              │
├─────────────────────────────────────────────────────────────┤
│ + getUsers(req: AuthRequest, res: Response): Promise<void>   │
│ + getUserById(req: AuthRequest, res: Response): Promise<void>│
│ + updateUserRole(req: AuthRequest, res: Response): Promise   │
│ + toggleUserStatus(req: AuthRequest, res: Response): Promise │
│ + deleteUser(req: AuthRequest, res: Response): Promise<void> │
│ + getAllAnalyses(req: AuthRequest, res: Response): Promise   │
│ + deleteAnalysis(req: AuthRequest, res: Response): Promise   │
│ + getAdminStats(req: AuthRequest, res: Response): Promise    │
└─────────────────────────────────────────────────────────────┘
```

### Backend Utilities

```
┌─────────────────────────────────────────────────────────────┐
│                    PasswordValidator                         │
├─────────────────────────────────────────────────────────────┤
│ + validatePassword(password: string): PasswordValidationResult│
│   - Checks: minLength (8), uppercase, lowercase, number      │
│   - Checks: special character                                │
│   - Returns: isValid, errors[], strength                     │
│                                                              │
│ + getPasswordRequirements(password: string): PasswordReqs    │
│   - Returns individual requirement status                    │
└─────────────────────────────────────────────────────────────┘
```

### Backend Middleware

```
┌─────────────────────────────────────────────────────────────┐
│                        AuthRequest                           │
│                    <<interface>> extends Request             │
├─────────────────────────────────────────────────────────────┤
│ + userId?: number                                            │
│ + userEmail?: string                                         │
│ + userRole?: string                                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      AuthMiddleware                          │
├─────────────────────────────────────────────────────────────┤
│ + authMiddleware(req, res, next): void                       │
│   - Extracts JWT from Authorization header                   │
│   - Validates token signature and expiry                     │
│   - Populates req.userId, req.userEmail, req.userRole        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      AdminMiddleware                         │
├─────────────────────────────────────────────────────────────┤
│ + adminMiddleware(req, res, next): void                      │
│   - Checks if req.userRole === 'admin'                       │
│   - Returns 403 if not admin                                 │
└─────────────────────────────────────────────────────────────┘
```

### Frontend Components

```
┌─────────────────────────────────────────────────────────────┐
│                      AuthProvider                            │
│                    <<React Context>>                         │
├─────────────────────────────────────────────────────────────┤
│ - user: User | null                                          │
│ - token: string | null                                       │
│ - isLoading: boolean                                         │
├─────────────────────────────────────────────────────────────┤
│ + login(email: string, password: string): Promise<void>      │
│ + register(email, password, fullName): Promise<void>         │
│ + logout(): void                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                         Login                                │
│                    <<React Component>>                       │
├─────────────────────────────────────────────────────────────┤
│ State:                                                       │
│ - email: string                                              │
│ - password: string                                           │
│ - isLoading: boolean                                         │
│ - error: string | null                                       │
├─────────────────────────────────────────────────────────────┤
│ + handleSubmit(data: LoginForm): Promise<void>               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        Register                              │
│                    <<React Component>>                       │
├─────────────────────────────────────────────────────────────┤
│ State:                                                       │
│ - fullName: string                                           │
│ - email: string                                              │
│ - password: string                                           │
│ - confirmPassword: string                                    │
│ - isLoading: boolean                                         │
│ - error: string | null                                       │
├─────────────────────────────────────────────────────────────┤
│ + handleSubmit(data: RegisterForm): Promise<void>            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                       Dashboard                              │
│                    <<React Component>>                       │
├─────────────────────────────────────────────────────────────┤
│ State:                                                       │
│ - stats: StatsResponse | null                                │
│ - isLoading: boolean                                         │
│ - error: string | null                                       │
├─────────────────────────────────────────────────────────────┤
│ + useEffect(): void  (fetches stats on mount)                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                       TextInput                              │
│                    <<React Component>>                       │
├─────────────────────────────────────────────────────────────┤
│ State:                                                       │
│ - activeTab: 'text' | 'pdf' | 'doc' | 'image' | 'voice'     │
│ - text: string                                               │
│ - title: string                                              │
│ - isLoading: boolean                                         │
│ - error: string | null                                       │
│ - success: string | null                                     │
│ - isRecording: boolean                                       │
├─────────────────────────────────────────────────────────────┤
│ + handleFileUpload(file: File): Promise<void>                │
│ + startRecording(): void                                     │
│ + stopRecording(): void                                      │
│ + handleAnalyze(): Promise<void>                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        History                               │
│                    <<React Component>>                       │
├─────────────────────────────────────────────────────────────┤
│ State:                                                       │
│ - analyses: AnalysisListItem[]                               │
│ - pagination: Pagination                                     │
│ - search: string                                             │
│ - gradeFilter: string                                        │
│ - deleteId: number | null                                    │
│ - isLoading: boolean                                         │
├─────────────────────────────────────────────────────────────┤
│ + fetchAnalyses(): Promise<void>                             │
│ + handleSearch(query: string): void                          │
│ + handleFilter(grade: string): void                          │
│ + handleDelete(id: number): Promise<void>                    │
│ + handlePageChange(page: number): void                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    AnalysisResults                           │
│                    <<React Component>>                       │
├─────────────────────────────────────────────────────────────┤
│ State:                                                       │
│ - analysis: SavedAnalysis | null                             │
│ - isLoading: boolean                                         │
│ - error: string | null                                       │
├─────────────────────────────────────────────────────────────┤
│ + useEffect(): void  (fetches analysis by ID)                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    HighlightedText                           │
│                    <<React Component>>                       │
├─────────────────────────────────────────────────────────────┤
│ Props:                                                       │
│ - text: string                                               │
│ - difficultWords: DifficultWord[]                            │
│ - difficultSentences: DifficultSentence[]                    │
├─────────────────────────────────────────────────────────────┤
│ + renderHighlightedText(): ReactNode                         │
└─────────────────────────────────────────────────────────────┘
```

### Frontend Chart Components

```
┌─────────────────────────────────────────────────────────────┐
│                         Charts                               │
│                    <<React Components>>                      │
├─────────────────────────────────────────────────────────────┤
│ Components:                                                  │
│ + ReadabilityRadarChart                                      │
│   - data: ReadabilityScores                                  │
│   - Displays 5 readability metrics on radar chart            │
│                                                              │
│ + TextStatsBarChart                                          │
│   - data: BasicMetrics                                       │
│   - Bar chart showing word/sentence statistics               │
│                                                              │
│ + GradeLevelGauge                                            │
│   - gradeLevel: string                                       │
│   - Semi-circular gauge for grade level                      │
│                                                              │
│ + WordDifficultyPieChart                                     │
│   - percentage: number                                       │
│   - Pie chart: common vs difficult words                     │
│                                                              │
│ + DifficultWordsChart                                        │
│   - words: DifficultWord[]                                   │
│   - Horizontal bar chart of difficult words                  │
└─────────────────────────────────────────────────────────────┘
```

### Frontend API Services

```
┌─────────────────────────────────────────────────────────────┐
│                         authApi                              │
│                      <<Service Object>>                      │
├─────────────────────────────────────────────────────────────┤
│ + register(email, password, fullName): Promise<AuthResponse> │
│ + login(email, password): Promise<AuthResponse>              │
│ + getMe(): Promise<{ user: User }>                           │
│ + logout(): Promise<void>                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                       analysisApi                            │
│                      <<Service Object>>                      │
├─────────────────────────────────────────────────────────────┤
│ + analyze(text, title?): Promise<AnalysisResponse>           │
│ + getAnalyses(params): Promise<{analyses, pagination}>       │
│ + getAnalysis(id): Promise<SavedAnalysis>                    │
│ + deleteAnalysis(id): Promise<void>                          │
│ + getStats(): Promise<StatsResponse>                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                         textApi                              │
│                      <<Service Object>>                      │
├─────────────────────────────────────────────────────────────┤
│ + extractPdf(file: File): Promise<{text, pageCount}>         │
│ + extractDoc(file: File): Promise<{text}>                    │
│ + extractImage(file: File): Promise<{text, confidence}>      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                         adminApi                             │
│                      <<Service Object>>                      │
├─────────────────────────────────────────────────────────────┤
│ + getStats(): Promise<AdminStats>                            │
│ + getUsers(params): Promise<{users, pagination}>             │
│ + getUser(id): Promise<{user, stats}>                        │
│ + updateUserRole(id, role): Promise<{message, user}>         │
│ + toggleUserStatus(id): Promise<{message, user}>             │
│ + deleteUser(id): Promise<{message}>                         │
│ + getAnalyses(params): Promise<{analyses, pagination}>       │
│ + deleteAnalysis(id): Promise<{message}>                     │
└─────────────────────────────────────────────────────────────┘
```

### Frontend Utilities

```
┌─────────────────────────────────────────────────────────────┐
│                      exportPdf                               │
│                     <<Utility Module>>                       │
├─────────────────────────────────────────────────────────────┤
│ + exportAnalysisToPdf(data: ExportData): void                │
│   - Generates PDF report using jsPDF                         │
│   - Includes: summary, stats, readability scores             │
│   - Includes: difficult words/sentences, pagination          │
│   - Downloads file automatically                             │
└─────────────────────────────────────────────────────────────┘
```

### Python ML Service Classes

```
┌─────────────────────────────────────────────────────────────┐
│                      TextProcessor                           │
├─────────────────────────────────────────────────────────────┤
│ - dic: pyphen.Pyphen                                         │
├─────────────────────────────────────────────────────────────┤
│ + __init__(): None                                           │
│ + count_syllables(word: str): int                            │
│ + get_words(text: str): List[str]                            │
│ + get_sentences(text: str): List[str]                        │
│ + get_paragraphs(text: str): List[str]                       │
│ + is_difficult_word(word: str): bool                         │
│ + get_difficult_words(text: str): List[Dict]                 │
│ + get_difficult_sentences(text: str): List[Dict]             │
│ + calculate_basic_metrics(text: str): Dict                   │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ uses
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    FeatureExtractor                          │
├─────────────────────────────────────────────────────────────┤
│ - processor: TextProcessor                                   │
├─────────────────────────────────────────────────────────────┤
│ + __init__(): None                                           │
│ + extract_features(text: str): Dict                          │
│ + get_ml_features(text: str): List[float]                    │
│ + get_feature_names(): List[str]                             │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ uses
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    ReadabilityModel                          │
├─────────────────────────────────────────────────────────────┤
│ - rf_model: RandomForestRegressor | None                     │
│ - gb_model: GradientBoostingRegressor | None                 │
│ - feature_extractor: FeatureExtractor                        │
│ - is_trained: bool                                           │
├─────────────────────────────────────────────────────────────┤
│ + __init__(): None                                           │
│ + load_clear_corpus(corpus_path: str): pd.DataFrame          │
│ + prepare_training_data(df: DataFrame): Tuple[ndarray]       │
│ + train(corpus_path: str): Dict                              │
│ + load_models(): bool                                        │
│ + predict(text: str): Dict                                   │
│ + save_models(): None                                        │
└─────────────────────────────────────────────────────────────┘
```

### TypeScript Interfaces (Frontend Types)

```
┌─────────────────────────────────────────────────────────────┐
│                          User                                │
│                       <<interface>>                          │
├─────────────────────────────────────────────────────────────┤
│ + id: number                                                 │
│ + email: string                                              │
│ + fullName: string                                           │
│ + createdAt: string                                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      BasicMetrics                            │
│                       <<interface>>                          │
├─────────────────────────────────────────────────────────────┤
│ + word_count: number                                         │
│ + sentence_count: number                                     │
│ + paragraph_count: number                                    │
│ + char_count: number                                         │
│ + avg_word_length: number                                    │
│ + avg_sentence_length: number                                │
│ + avg_syllables_per_word: number                             │
│ + total_syllables: number                                    │
│ + polysyllabic_words: number                                 │
│ + polysyllabic_percentage: number                            │
│ + type_token_ratio: number                                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   ReadabilityScores                          │
│                       <<interface>>                          │
├─────────────────────────────────────────────────────────────┤
│ + flesch_reading_ease: number                                │
│ + flesch_kincaid_grade: number                               │
│ + automated_readability_index: number                        │
│ + smog_readability: number                                   │
│ + coleman_liau_index: number                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      Predictions                             │
│                       <<interface>>                          │
├─────────────────────────────────────────────────────────────┤
│ + predicted_grade_level: string                              │
│ + predicted_complexity: string                               │
│ + confidence: number                                         │
│ + raw_score?: number                                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     DifficultWord                            │
│                       <<interface>>                          │
├─────────────────────────────────────────────────────────────┤
│ + word: string                                               │
│ + position: number                                           │
│ + syllables: number                                          │
│ + reason: string                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   DifficultSentence                          │
│                       <<interface>>                          │
├─────────────────────────────────────────────────────────────┤
│ + sentence: string                                           │
│ + position: number                                           │
│ + word_count: number                                         │
│ + reason: string                                             │
│ + flesch_score: number                                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        Analysis                              │
│                       <<interface>>                          │
├─────────────────────────────────────────────────────────────┤
│ + basic_metrics: BasicMetrics                                │
│ + readability_scores: ReadabilityScores                      │
│ + predictions: Predictions                                   │
│ + difficult_elements: DifficultElements                      │
│ + statistics: Statistics                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     SavedAnalysis                            │
│                       <<interface>>                          │
├─────────────────────────────────────────────────────────────┤
│ + id: number                                                 │
│ + title: string                                              │
│ + originalText: string                                       │
│ + createdAt: string                                          │
│ + analysis: Analysis                                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   AnalysisListItem                           │
│                       <<interface>>                          │
├─────────────────────────────────────────────────────────────┤
│ + id: number                                                 │
│ + title: string                                              │
│ + word_count: number                                         │
│ + sentence_count: number                                     │
│ + flesch_reading_ease: number                                │
│ + predicted_grade_level: string                              │
│ + predicted_complexity: string                               │
│ + created_at: string                                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                       Pagination                             │
│                       <<interface>>                          │
├─────────────────────────────────────────────────────────────┤
│ + page: number                                               │
│ + limit: number                                              │
│ + totalCount: number                                         │
│ + totalPages: number                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## API Endpoints Reference

### Authentication (`/api/auth`)

| Method | Endpoint | Auth Required | Description |
|--------|----------|---------------|-------------|
| POST | `/register` | No | Create new user account |
| POST | `/login` | No | Authenticate user |
| GET | `/me` | Yes | Get current user profile |
| POST | `/logout` | No | Logout (client-side) |

### Analyses (`/api/analyses`)

| Method | Endpoint | Auth Required | Description |
|--------|----------|---------------|-------------|
| POST | `/` | Yes | Create new text analysis |
| GET | `/` | Yes | List analyses (paginated) |
| GET | `/:id` | Yes | Get analysis by ID |
| DELETE | `/:id` | Yes | Delete analysis |
| GET | `/stats` | Yes | Get user statistics |

### Text Extraction (`/api/text`)

| Method | Endpoint | Auth Required | Description |
|--------|----------|---------------|-------------|
| POST | `/extract-pdf` | Yes | Extract text from PDF |
| POST | `/extract-doc` | Yes | Extract text from DOC/DOCX |
| POST | `/extract-image` | Yes | Extract text from image (OCR) |

### Admin (`/api/admin`) - Requires Admin Role

| Method | Endpoint | Auth Required | Description |
|--------|----------|---------------|-------------|
| GET | `/stats` | Admin | Get platform-wide statistics |
| GET | `/users` | Admin | List all users (paginated, searchable) |
| GET | `/users/:id` | Admin | Get user details with stats |
| PATCH | `/users/:id/role` | Admin | Update user role (user/admin) |
| PATCH | `/users/:id/status` | Admin | Toggle user active status |
| DELETE | `/users/:id` | Admin | Delete user and their data |
| GET | `/analyses` | Admin | List all analyses (paginated) |
| DELETE | `/analyses/:id` | Admin | Delete any analysis |

---

## Password Requirements

The system enforces the following password requirements:

| Requirement | Description |
|-------------|-------------|
| Minimum Length | At least 8 characters |
| Uppercase | At least one uppercase letter (A-Z) |
| Lowercase | At least one lowercase letter (a-z) |
| Number | At least one digit (0-9) |
| Special Character | At least one special character (!@#$%^&*()_+-=[]{};\':\"\\|,.<>/?) |

Password strength is calculated based on the number of requirements met:
- **Weak**: 0-2 requirements met
- **Fair**: 3 requirements met
- **Good**: 4 requirements met
- **Strong**: All 5 requirements met (bonus for 12+ character passwords)

---

*Document generated for ClarityWorks v2.0*