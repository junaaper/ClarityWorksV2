# ClarityWorks - Quick Reference Guide

## Where Everything Happens

### 🔐 AUTHENTICATION & SECURITY

| What | Where | File:Line |
|------|-------|-----------|
| **Login Logic** | Backend Controller | [backend/src/controllers/authController.ts:33-66](backend/src/controllers/authController.ts#L33-L66) |
| **Registration Logic** | Backend Controller | [backend/src/controllers/authController.ts:8-31](backend/src/controllers/authController.ts#L8-L31) |
| **Password Hashing** | Auth Controller (bcrypt) | [backend/src/controllers/authController.ts:14](backend/src/controllers/authController.ts#L14) |
| **Password Validation Rules** | Password Validator | [backend/src/utils/passwordValidator.ts:3-46](backend/src/utils/passwordValidator.ts#L3-L46) |
| **Password Strength Checking** | Password Validator | [backend/src/utils/passwordValidator.ts:48-68](backend/src/utils/passwordValidator.ts#L48-L68) |
| **JWT Token Generation** | Auth Controller | [backend/src/controllers/authController.ts:24-29](backend/src/controllers/authController.ts#L24-L29) |
| **JWT Token Verification** | Auth Middleware | [backend/src/middleware/auth.ts:8-26](backend/src/middleware/auth.ts#L8-L26) |
| **Admin Authorization** | Auth Middleware | [backend/src/middleware/auth.ts:28-36](backend/src/middleware/auth.ts#L28-L36) |
| **Auth Routes** | Route Definition | [backend/src/routes/authRoutes.ts](backend/src/routes/authRoutes.ts) |

**Password Requirements:**
- Minimum 8 characters
- 1 uppercase, 1 lowercase, 1 digit, 1 special character
- Located: [backend/src/utils/passwordValidator.ts:11-17](backend/src/utils/passwordValidator.ts#L11-L17)

---

### 🗄️ DATABASE

| What | Where | File:Line |
|------|-------|-----------|
| **Database Connection** | Database Config | [backend/src/config/database.ts:6-11](backend/src/config/database.ts#L6-L11) |
| **Database Schema (Users)** | Database Init | [backend/src/config/database.ts:22-32](backend/src/config/database.ts#L22-L32) |
| **Database Schema (Analyses)** | Database Init | [backend/src/config/database.ts:51-75](backend/src/config/database.ts#L51-L75) |
| **Database Indexes** | Database Init | [backend/src/config/database.ts:78-83](backend/src/config/database.ts#L78-L83) |
| **Connection Pool Settings** | Database Config | [backend/src/config/database.ts:8-10](backend/src/config/database.ts#L8-L10) |

**Connection Pool:**
- Max connections: 20
- Idle timeout: 30 seconds
- Connection timeout: 2 seconds

---

### 🛣️ ROUTES & API ENDPOINTS

| What | Where | File |
|------|-------|------|
| **Auth Routes** | `/api/auth/*` | [backend/src/routes/authRoutes.ts](backend/src/routes/authRoutes.ts) |
| **Analysis Routes** | `/api/analyses/*` | [backend/src/routes/analysisRoutes.ts](backend/src/routes/analysisRoutes.ts) |
| **Text Extraction Routes** | `/api/text/*` | [backend/src/routes/textRoutes.ts](backend/src/routes/textRoutes.ts) |
| **Admin Routes** | `/api/admin/*` | [backend/src/routes/adminRoutes.ts](backend/src/routes/adminRoutes.ts) |
| **Server Entry Point** | Main Server | [backend/src/server.ts](backend/src/server.ts) |

---

### 📊 TEXT ANALYSIS & SCORING

#### Main Analysis Flow

| What | Where | File:Line |
|------|-------|-----------|
| **Analysis Request Handler** | Backend Controller | [backend/src/controllers/analysisController.ts:8-78](backend/src/controllers/analysisController.ts#L8-L78) |
| **Call to ML Service** | Backend Controller | [backend/src/controllers/analysisController.ts:24-26](backend/src/controllers/analysisController.ts#L24-L26) |
| **Save Analysis to DB** | Backend Controller | [backend/src/controllers/analysisController.ts:31-62](backend/src/controllers/analysisController.ts#L31-L62) |

#### ML Service - Scoring Logic

| What | Where | File:Line |
|------|-------|-----------|
| **ML Service Entry Point** | Flask App | [ml-service/app.py](ml-service/app.py) |
| **Analysis Endpoint** | Flask Route | [ml-service/app.py:40-51](ml-service/app.py#L40-L51) |
| **Prediction Pipeline** | Readability Model | [ml-service/models/readability_model.py:165-207](ml-service/models/readability_model.py#L165-L207) |

#### Readability Scores

| Score Type | Where | File:Line |
|------------|-------|-----------|
| **Flesch Reading Ease** | Feature Extractor | [ml-service/models/feature_extractor.py:15](ml-service/models/feature_extractor.py#L15) |
| **Flesch-Kincaid Grade** | Feature Extractor | [ml-service/models/feature_extractor.py:16](ml-service/models/feature_extractor.py#L16) |
| **ARI (Automated Readability Index)** | Feature Extractor | [ml-service/models/feature_extractor.py:17](ml-service/models/feature_extractor.py#L17) |
| **SMOG Index** | Feature Extractor | [ml-service/models/feature_extractor.py:18](ml-service/models/feature_extractor.py#L18) |
| **Coleman-Liau Index** | Feature Extractor | [ml-service/models/feature_extractor.py:19](ml-service/models/feature_extractor.py#L19) |
| **Dale-Chall Score** | Feature Extractor | [ml-service/models/feature_extractor.py:20](ml-service/models/feature_extractor.py#L20) |
| **Linsear Write** | Feature Extractor | [ml-service/models/feature_extractor.py:21](ml-service/models/feature_extractor.py#L21) |
| **Gunning Fog** | Feature Extractor | [ml-service/models/feature_extractor.py:22](ml-service/models/feature_extractor.py#L22) |

#### Sentence-Level Flesch Score

| What | Where | File:Line |
|------|-------|-----------|
| **Flesch Score Calculation** | Text Processor | [ml-service/models/text_processor.py:256-264](ml-service/models/text_processor.py#L256-L264) |
| **Flesch Score Clamping (0-100)** | Text Processor | [ml-service/models/text_processor.py:262](ml-service/models/text_processor.py#L262) |
| **Flesch Formula** | Text Processor | [ml-service/models/text_processor.py:260](ml-service/models/text_processor.py#L260) |

**Formula:** `206.835 - 1.015 × (words/sentence) - 84.6 × (syllables/word)`

---

### 🔤 TEXT PROCESSING & TOKENIZATION

| What | Where | File:Line |
|------|-------|-----------|
| **Word Tokenization** | Text Processor | [ml-service/models/text_processor.py:142-147](ml-service/models/text_processor.py#L142-L147) |
| **Sentence Tokenization** | Text Processor | [ml-service/models/text_processor.py:149-153](ml-service/models/text_processor.py#L149-L153) |
| **Paragraph Tokenization** | Text Processor | [ml-service/models/text_processor.py:155-158](ml-service/models/text_processor.py#L155-L158) |
| **Syllable Counting** | Text Processor | [ml-service/models/text_processor.py:128-140](ml-service/models/text_processor.py#L128-L140) |

**Tokenization Method:**
- Words: Regex pattern `[^\w\s']` (removes punctuation except apostrophes)
- Sentences: Split on `.!?`
- Paragraphs: Split on double newlines `\n\s*\n`

---

### 🎯 DIFFICULTY DETECTION

| What | Where | File:Line |
|------|-------|-----------|
| **Difficult Word Detection** | Text Processor | [ml-service/models/text_processor.py:201-233](ml-service/models/text_processor.py#L201-L233) |
| **Difficult Sentence Detection** | Text Processor | [ml-service/models/text_processor.py:235-285](ml-service/models/text_processor.py#L235-L285) |
| **Dale-Chall Word List** | Text Processor | [ml-service/models/text_processor.py:6-122](ml-service/models/text_processor.py#L6-L122) |
| **Proper Noun Detection** | Text Processor | [ml-service/models/text_processor.py:160-174](ml-service/models/text_processor.py#L160-L174) |
| **Difficulty Check Logic** | Text Processor | [ml-service/models/text_processor.py:176-199](ml-service/models/text_processor.py#L176-L199) |

**Difficulty Criteria (Words):**
- Not in Dale-Chall 3000 common words
- 4+ characters long
- 3+ syllables
- Not a proper noun or abbreviation

**Difficulty Criteria (Sentences):**
- 25+ words (long sentence)
- Flesch < 30 AND 2+ difficult words
- 3+ difficult words
- 5+ polysyllabic words

---

### 📄 FILE EXTRACTION

| What | Where | File:Line |
|------|-------|-----------|
| **PDF Extraction** | Python ML Service | [ml-service/app.py:54-65](ml-service/app.py#L54-L65) |
| **DOC/DOCX Extraction** | Python ML Service | [ml-service/app.py:68-78](ml-service/app.py#L68-L78) |
| **Image OCR** | Python ML Service | [ml-service/app.py:81-104](ml-service/app.py#L81-L104) |
| **Backend PDF Route** | Text Controller | [backend/src/controllers/textController.ts:8-34](backend/src/controllers/textController.ts#L8-L34) |
| **Backend DOC Route** | Text Controller | [backend/src/controllers/textController.ts:36-62](backend/src/controllers/textController.ts#L36-L62) |
| **Backend Image Route** | Text Controller | [backend/src/controllers/textController.ts:64-90](backend/src/controllers/textController.ts#L64-L90) |
| **File Upload Config** | Multer Config | [backend/src/config/upload.ts](backend/src/config/upload.ts) |

**Technologies:**
- PDF: `pdfplumber` (Python)
- DOC/DOCX: `python-docx` (Python)
- Images: `pytesseract` (Tesseract OCR)

---

### 🤖 MACHINE LEARNING

| What | Where | File:Line |
|------|-------|-----------|
| **ML Model Class** | Readability Model | [ml-service/models/readability_model.py:11-259](ml-service/models/readability_model.py#L11-L259) |
| **Feature Extraction** | Feature Extractor | [ml-service/models/feature_extractor.py:9-80](ml-service/models/feature_extractor.py#L9-L80) |
| **11 ML Features** | Feature Extractor | [ml-service/models/feature_extractor.py:48-64](ml-service/models/feature_extractor.py#L48-L64) |
| **Random Forest Model** | Readability Model | [ml-service/models/readability_model.py:99-105](ml-service/models/readability_model.py#L99-L105) |
| **Gradient Boosting Model** | Readability Model | [ml-service/models/readability_model.py:108-115](ml-service/models/readability_model.py#L108-L115) |
| **Ensemble Prediction** | Readability Model | [ml-service/models/readability_model.py:172-175](ml-service/models/readability_model.py#L172-L175) |
| **Confidence Calculation** | Readability Model | [ml-service/models/readability_model.py:178-179](ml-service/models/readability_model.py#L178-L179) |
| **Grade Level Conversion** | Readability Model | [ml-service/models/readability_model.py:209-234](ml-service/models/readability_model.py#L209-L234) |
| **Complexity Categorization** | Readability Model | [ml-service/models/readability_model.py:236-258](ml-service/models/readability_model.py#L236-L258) |
| **Model Training** | Readability Model | [ml-service/models/readability_model.py:82-137](ml-service/models/readability_model.py#L82-L137) |
| **Training Script** | Python Script | [ml-service/train_model.py](ml-service/train_model.py) |

**11 Features:**
1. word_count
2. sentence_count
3. avg_sentence_length
4. avg_word_length
5. avg_syllables_per_word
6. difficult_words_percentage
7. flesch_reading_ease
8. flesch_kincaid_grade
9. automated_readability_index
10. smog_readability
11. type_token_ratio

**Complexity Levels:**
- Beginner: Grades 3-6
- Intermediate: Grades 7-9
- Advanced: Grades 10-12
- Expert: College+

---

### 📊 BASIC METRICS CALCULATION

| What | Where | File:Line |
|------|-------|-----------|
| **All Basic Metrics** | Text Processor | [ml-service/models/text_processor.py:287-268](ml-service/models/text_processor.py#L287-L268) |
| **Word Count** | Text Processor | [ml-service/models/text_processor.py:238](ml-service/models/text_processor.py#L238) |
| **Sentence Count** | Text Processor | [ml-service/models/text_processor.py:239](ml-service/models/text_processor.py#L239) |
| **Average Word Length** | Text Processor | [ml-service/models/text_processor.py:243](ml-service/models/text_processor.py#L243) |
| **Average Sentence Length** | Text Processor | [ml-service/models/text_processor.py:244](ml-service/models/text_processor.py#L244) |
| **Syllables per Word** | Text Processor | [ml-service/models/text_processor.py:247](ml-service/models/text_processor.py#L247) |
| **Polysyllabic Words** | Text Processor | [ml-service/models/text_processor.py:249-250](ml-service/models/text_processor.py#L249-L250) |
| **Type-Token Ratio** | Text Processor | [ml-service/models/text_processor.py:253-254](ml-service/models/text_processor.py#L253-L254) |

---

### 🎨 FRONTEND

| What | Where | File |
|------|-------|------|
| **App Entry Point** | Main App | [frontend/src/main.tsx](frontend/src/main.tsx) |
| **Router Configuration** | App Component | [frontend/src/App.tsx](frontend/src/App.tsx) |
| **Auth Context** | Auth Provider | [frontend/src/utils/auth.tsx](frontend/src/utils/auth.tsx) |
| **API Client** | API Service | [frontend/src/services/api.ts](frontend/src/services/api.ts) |
| **Login Component** | Auth Component | [frontend/src/components/Auth/Login.tsx](frontend/src/components/Auth/Login.tsx) |
| **Register Component** | Auth Component | [frontend/src/components/Auth/Register.tsx](frontend/src/components/Auth/Register.tsx) |
| **Dashboard Component** | Dashboard | [frontend/src/components/Dashboard/Dashboard.tsx](frontend/src/components/Dashboard/Dashboard.tsx) |
| **Text Input Component** | Text Input | [frontend/src/components/TextInput/TextInput.tsx](frontend/src/components/TextInput/TextInput.tsx) |
| **Analysis Results Component** | Analysis | [frontend/src/components/Analysis/AnalysisResults.tsx](frontend/src/components/Analysis/AnalysisResults.tsx) |
| **Charts Component** | Analysis | [frontend/src/components/Analysis/Charts.tsx](frontend/src/components/Analysis/Charts.tsx) |
| **History Component** | History | [frontend/src/components/History/History.tsx](frontend/src/components/History/History.tsx) |
| **Profile Component** | Profile | [frontend/src/components/Profile/Profile.tsx](frontend/src/components/Profile/Profile.tsx) |
| **Admin Dashboard** | Admin | [frontend/src/components/Admin/AdminDashboard.tsx](frontend/src/components/Admin/AdminDashboard.tsx) |

---

### 🔄 DATA FLOW

#### Complete Analysis Flow:

```
1. User Input
   └─> [frontend/src/components/TextInput/TextInput.tsx]

2. API Call
   └─> [frontend/src/services/api.ts] (analysisApi.analyze)

3. Backend Receives
   └─> [backend/src/routes/analysisRoutes.ts] (POST /api/analyses)
   └─> [backend/src/middleware/auth.ts] (JWT verification)
   └─> [backend/src/controllers/analysisController.ts:8] (analyzeText)

4. Call ML Service
   └─> [backend/src/controllers/analysisController.ts:24-26]
   └─> HTTP POST to Python service

5. ML Processing
   └─> [ml-service/app.py:40] (/analyze endpoint)
   └─> [ml-service/models/readability_model.py:165] (predict method)
        ├─> [ml-service/models/feature_extractor.py:9] (extract_features)
        │   └─> [ml-service/models/text_processor.py] (basic metrics)
        ├─> [ml-service/models/feature_extractor.py:48] (get_ml_features)
        └─> [ml-service/models/readability_model.py:172-175] (ensemble prediction)

6. Save to Database
   └─> [backend/src/controllers/analysisController.ts:31-62]
   └─> PostgreSQL INSERT

7. Return to Frontend
   └─> [frontend/src/components/Analysis/AnalysisResults.tsx]
   └─> Display results with charts
```

---

### 📦 CONFIGURATION FILES

| What | Where | File |
|------|-------|------|
| **Backend Environment** | Backend Root | [backend/.env](backend/.env) |
| **Frontend Environment** | Frontend Root | [frontend/.env](frontend/.env) |
| **ML Service Environment** | ML Service Root | [ml-service/.env](ml-service/.env) |
| **Backend Package Config** | Backend Root | [backend/package.json](backend/package.json) |
| **Frontend Package Config** | Frontend Root | [frontend/package.json](frontend/package.json) |
| **Python Dependencies** | ML Service Root | [ml-service/requirements.txt](ml-service/requirements.txt) |
| **TypeScript Config (Backend)** | Backend Root | [backend/tsconfig.json](backend/tsconfig.json) |
| **TypeScript Config (Frontend)** | Frontend Root | [frontend/tsconfig.json](frontend/tsconfig.json) |
| **Vite Config** | Frontend Root | [frontend/vite.config.ts](frontend/vite.config.ts) |
| **Tailwind Config** | Frontend Root | [frontend/tailwind.config.js](frontend/tailwind.config.js) |

---

### 🧪 TESTING

| What | Where | File |
|------|-------|------|
| **Test Improvements Script** | ML Service | [testing/ml-service/test_improvements.py](testing/ml-service/test_improvements.py) |
| **Query Users Script** | Backend | [backend/query_users.js](backend/query_users.js) |

---

### 📖 DOCUMENTATION

| What | Where | File |
|------|-------|------|
| **Main README** | Project Root | [README.md](README.md) |
| **Setup Guide** | README | [README.md:72-387](README.md#L72-L387) |
| **API Reference** | README | [README.md:467-502](README.md#L467-L502) |
| **Technical Explanation** | Project Root | [EXPLANATION.md](EXPLANATION.md) |
| **Recent Improvements** | Project Root | [IMPROVEMENTS.md](IMPROVEMENTS.md) |
| **This Quick Reference** | Project Root | [Simple.md](Simple.md) |

---

## Quick Commands Reference

### Start All Services

```bash
# Terminal 1 - Backend (Port 5000)
cd backend
npm run dev

# Terminal 2 - ML Service (Port 5001)
cd ml-service
./venv/Scripts/python.exe app.py

# Terminal 3 - Frontend (Port 5173)
cd frontend
npm run dev
```

### Database Query

```bash
cd backend
node query_users.js
```

### Test ML Improvements

```bash
cd ml-service
./ml-service/venv/Scripts/python.exe testing/ml-service/test_improvements.py
```

---

## Environment Variables

### Backend (.env)
```
PORT=5000
DATABASE_URL=postgresql://clarityworks_user:clarityworks_pass@localhost:5432/clarityworks_db
JWT_SECRET=your_super_secret_jwt_key_change_this_in_production
PYTHON_SERVICE_URL=http://localhost:5001
```

### Frontend (.env)
```
VITE_API_URL=http://localhost:5000
VITE_PYTHON_API_URL=http://localhost:5001
```

### ML Service (.env)
```
FLASK_PORT=5001
TESSERACT_PATH=C:/Program Files/Tesseract-OCR/tesseract.exe
```

---

*Last Updated: 2024-12-11*
*Quick Reference for ClarityWorks v2*
