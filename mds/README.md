# ClarityWorks - Text Readability Analysis

A comprehensive text readability analysis web application that uses the CLEAR Corpus dataset and traditional readability metrics. Built as a Computer Science Final Year Project.

## Features

- **Multiple Input Methods**: Text paste, PDF upload, DOC/DOCX upload, Image OCR, Voice recording
- **Comprehensive Analysis**: Multiple readability scores including Flesch, SMOG, ARI, Coleman-Liau
- **Machine Learning**: Grade level prediction using ensemble models trained on CLEAR Corpus
- **Visualizations**: Interactive charts with Recharts (radar, bar, pie, gauge)
- **Text Highlighting**: Difficult words and sentences highlighted with explanations
- **History Management**: Save, search, filter, and manage past analyses
- **Authentication**: Secure JWT-based user authentication

## Tech Stack

- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, Recharts
- **Backend**: Node.js, Express.js, TypeScript, PostgreSQL
- **ML Service**: Python, Flask, scikit-learn, textstat

---

## Prerequisites

Before starting, ensure you have the following installed:

### 1. Node.js (v18 or higher)
- Download from: https://nodejs.org/
- Verify installation:
  ```bash
  node --version
  npm --version
  ```

### 2. Python (v3.9 or higher)
- Download from: https://www.python.org/downloads/
- Verify installation:
  ```bash
  python --version
  pip --version
  ```

### 3. PostgreSQL (v14 or higher)
- **Windows**: Download installer from https://www.postgresql.org/download/windows/
- **Mac**: `brew install postgresql@14` or download from https://www.postgresql.org/download/macosx/
- **Linux (Ubuntu/Debian)**:
  ```bash
  sudo apt update
  sudo apt install postgresql postgresql-contrib
  ```
- Verify installation:
  ```bash
  psql --version
  ```

### 4. Tesseract OCR (for image text extraction)
- **Windows**:
  1. Download installer from https://github.com/UB-Mannheim/tesseract/wiki
  2. Run the installer (default path: `C:\Program Files\Tesseract-OCR`)
  3. Note the installation path for later configuration
- **Mac**:
  ```bash
  brew install tesseract
  ```
- **Linux (Ubuntu/Debian)**:
  ```bash
  sudo apt install tesseract-ocr
  ```

---

## Step-by-Step Installation Guide

### Step 1: Clone/Download the Project

```bash
cd c:/Programming/clarityworksv2
```

### Step 2: PostgreSQL Database Setup

#### 2.1 Start PostgreSQL Service

**Windows:**
- PostgreSQL should start automatically after installation
- Or open Services (Win+R, type `services.msc`) and start "postgresql-x64-14"

**Mac:**
```bash
brew services start postgresql@14
```

**Linux:**
```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql  # Auto-start on boot
```

#### 2.2 Access PostgreSQL Command Line

**Windows (using pgAdmin or psql):**
```bash
# Open Command Prompt as Administrator
psql -U postgres
```
Enter the password you set during installation.

**Mac/Linux:**
```bash
sudo -u postgres psql
```

#### 2.3 Create Database and User

Run these SQL commands one by one:

```sql
-- Create the database
CREATE DATABASE clarityworks_db;

-- Create the user with password
CREATE USER clarityworks_user WITH PASSWORD 'clarityworks_pass';

-- Grant privileges on the database
GRANT ALL PRIVILEGES ON DATABASE clarityworks_db TO clarityworks_user;

-- Connect to the new database
\c clarityworks_db

-- Grant schema privileges (required for PostgreSQL 15+)
GRANT ALL ON SCHEMA public TO clarityworks_user;
GRANT CREATE ON SCHEMA public TO clarityworks_user;

-- Exit psql
\q
```

#### 2.4 Verify Database Connection

```bash
psql -U clarityworks_user -d clarityworks_db -h localhost
```
Enter password: `clarityworks_pass`

If you can connect, the database is set up correctly. Type `\q` to exit.

---

### Step 3: Database Schema

The tables are created automatically when the backend starts, but here's the complete schema for reference:

```sql
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Analyses table
CREATE TABLE IF NOT EXISTS analyses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    original_text TEXT NOT NULL,
    title VARCHAR(255),
    word_count INTEGER,
    sentence_count INTEGER,
    avg_sentence_length DECIMAL,
    avg_syllables_per_word DECIMAL,
    flesch_reading_ease DECIMAL,
    flesch_kincaid_grade DECIMAL,
    automated_readability_index DECIMAL,
    smog_readability DECIMAL,
    coleman_liau_index DECIMAL,
    predicted_grade_level VARCHAR(50),
    predicted_complexity VARCHAR(50),
    confidence DECIMAL,
    difficult_words_count INTEGER,
    difficult_words_percentage DECIMAL,
    difficult_words JSONB,
    difficult_sentences JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC);
```

---

### Step 4: Backend Setup (Node.js/Express)

#### 4.1 Navigate to Backend Directory

```bash
cd backend
```

#### 4.2 Install Dependencies

```bash
npm install
```

This installs: express, cors, pg, bcrypt, jsonwebtoken, multer, axios, and TypeScript dependencies.

#### 4.3 Configure Environment Variables

The `.env` file should already exist with these contents:

```env
PORT=5000
DATABASE_URL=postgresql://clarityworks_user:clarityworks_pass@localhost:5432/clarityworks_db
JWT_SECRET=your_super_secret_jwt_key_change_this_in_production
PYTHON_SERVICE_URL=http://localhost:5001
NODE_ENV=development
```

**Important:** For production, change `JWT_SECRET` to a secure random string.

#### 4.4 Test Backend Setup

```bash
npm run dev
```

You should see:
```
Database tables initialized successfully
Server running on port 5000
Health check: http://localhost:5000/api/health
```

Press `Ctrl+C` to stop for now.

---

### Step 5: Python ML Service Setup

#### 5.1 Navigate to ML Service Directory

```bash
cd ../ml-service
```

#### 5.2 Create Virtual Environment (Recommended)

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

#### 5.3 Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs: flask, flask-cors, scikit-learn, pandas, numpy, textstat, pyphen, pdfplumber, python-docx, pytesseract, Pillow, joblib.

#### 5.4 Configure Environment Variables

Edit `.env` file. **Windows users**: Update the Tesseract path:

```env
FLASK_PORT=5001
FLASK_ENV=development
TESSERACT_PATH=C:/Program Files/Tesseract-OCR/tesseract.exe
```

**Mac/Linux users**: You can usually leave the path empty or set it to:
```env
TESSERACT_PATH=/usr/bin/tesseract
```

#### 5.5 Test ML Service Setup

```bash
python app.py
```

You should see:
```
Warning: No trained models found. Using heuristic predictions.
 * Running on http://0.0.0.0:5001
```

Press `Ctrl+C` to stop for now.

---

### Step 6: Frontend Setup (React/Vite)

#### 6.1 Navigate to Frontend Directory

```bash
cd ../frontend
```

#### 6.2 Install Dependencies

```bash
npm install
```

This installs: react, react-router-dom, axios, recharts, tailwindcss, lucide-react, and other dependencies.

#### 6.3 Configure Environment Variables

The `.env` file should already exist:

```env
VITE_API_URL=http://localhost:5000
VITE_PYTHON_API_URL=http://localhost:5001
```

#### 6.4 Test Frontend Setup

```bash
npm run dev
```

You should see:
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
```

---

### Step 7: CLEAR Corpus Dataset (Optional - For ML Training)

The application works without trained models using heuristic predictions based on readability formulas. However, for better predictions:

#### 7.1 Download CLEAR Corpus

1. Go to: https://www.commonlit.org/en/research/clear-corpus
2. Click "Download the CLEAR Corpus" button
3. You'll receive a CSV file with ~5000 text excerpts

#### 7.2 Place the Dataset

Move the CSV file to:
```
ml-service/data/clear_corpus/clear_corpus.csv
```

#### 7.3 Train the Model

```bash
cd ml-service
python train_model.py
```

Or if using virtual environment:
```bash
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux
python train_model.py
```

Expected output:
```
Loading CLEAR Corpus...
Loaded 4799 samples
Preparing training data...
Training Random Forest...
Training Gradient Boosting...
Ensemble RMSE: 0.xxxx
Ensemble R²: 0.xxxx
Models saved to trained_models/
```

---

## Running the Application

You need **three terminal windows** running simultaneously:

### Terminal 1 - Backend (Port 5000)

```bash
cd backend
npm run dev
```

### Terminal 2 - Python ML Service (Port 5001)

```bash
cd ml-service
# If using virtual environment:
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
python app.py
```

### Terminal 3 - Frontend (Port 5173)

```bash
cd frontend
npm run dev
```

### Access the Application

Open your browser and go to: **http://localhost:5173**

---

## Testing the Application

### 1. Create an Account
- Click "Sign up" on the login page
- Enter your name, email, and password
- You'll be redirected to the dashboard

### 2. Test Text Analysis
- Click "Start New Analysis" or "New Analysis" in the sidebar
- Try each input method:

  **Manual Text:**
  - Paste any text (minimum 50 characters)
  - Example: Copy a paragraph from a news article

  **PDF Upload:**
  - Upload any PDF file
  - Text will be extracted automatically

  **DOC/DOCX Upload:**
  - Upload a Word document
  - Text will be extracted automatically

  **Image (OCR):**
  - Upload an image containing text (screenshot, scanned document)
  - Requires Tesseract to be properly installed

  **Voice:**
  - Click the microphone button
  - Speak into your microphone
  - Works best in Chrome/Edge browsers

### 3. View Results
- After analysis, you'll see:
  - Grade level prediction
  - Readability scores (Flesch, SMOG, ARI, etc.)
  - Interactive charts
  - Highlighted difficult words and sentences

### 4. Check History
- Click "History" in the sidebar
- View, search, and delete past analyses

---

## API Endpoints Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login user |
| GET | `/api/auth/me` | Get current user (protected) |
| POST | `/api/auth/logout` | Logout user |

### Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analyses` | Analyze text |
| GET | `/api/analyses` | Get user's analyses (paginated) |
| GET | `/api/analyses/stats` | Get user statistics |
| GET | `/api/analyses/:id` | Get specific analysis |
| DELETE | `/api/analyses/:id` | Delete analysis |

### Text Extraction
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/text/extract-pdf` | Extract text from PDF |
| POST | `/api/text/extract-doc` | Extract text from DOC/DOCX |
| POST | `/api/text/extract-image` | Extract text from image (OCR) |

### Python ML Service
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/analyze` | Analyze text and return metrics |
| POST | `/extract-pdf` | Extract text from PDF |
| POST | `/extract-doc` | Extract text from DOC/DOCX |
| POST | `/extract-image` | OCR text extraction |
| POST | `/train` | Train ML model (with corpus path) |

---

## Project Structure

```
clarityworks/
├── frontend/                     # React application
│   ├── src/
│   │   ├── components/
│   │   │   ├── Auth/            # Login, Register
│   │   │   ├── Dashboard/       # Main dashboard
│   │   │   ├── TextInput/       # Text input methods
│   │   │   ├── Analysis/        # Results, Charts, Highlighting
│   │   │   ├── History/         # History management
│   │   │   └── Layout/          # Sidebar, Layout wrapper
│   │   ├── services/            # API client (axios)
│   │   ├── types/               # TypeScript interfaces
│   │   └── utils/               # Auth context
│   ├── package.json
│   └── tailwind.config.js
│
├── backend/                      # Node.js/Express API
│   ├── src/
│   │   ├── routes/              # authRoutes, analysisRoutes, textRoutes
│   │   ├── controllers/         # Business logic
│   │   ├── middleware/          # JWT auth middleware
│   │   ├── config/              # Database connection
│   │   └── server.ts            # Express app entry point
│   ├── uploads/                 # Temporary file uploads
│   └── package.json
│
├── ml-service/                   # Python Flask microservice
│   ├── models/
│   │   ├── text_processor.py    # Syllable counting, word analysis
│   │   ├── feature_extractor.py # Feature extraction for ML
│   │   └── readability_model.py # Ensemble ML model
│   ├── data/
│   │   └── clear_corpus/        # Place CLEAR dataset here
│   ├── trained_models/          # Saved ML models (.joblib)
│   ├── app.py                   # Flask entry point
│   ├── train_model.py           # Training script
│   └── requirements.txt
│
└── README.md
```

---

## Readability Metrics Explained

| Metric | Range | Interpretation |
|--------|-------|----------------|
| **Flesch Reading Ease** | 0-100 | Higher = easier. 60-70 is standard, 0-30 is very difficult |
| **Flesch-Kincaid Grade** | 0-18+ | US grade level needed to understand the text |
| **SMOG Index** | 0-18+ | Years of education needed to comprehend |
| **Automated Readability Index** | 0-14+ | Grade level based on characters per word |
| **Coleman-Liau Index** | 0-18+ | Grade level based on letters and sentences |

### Complexity Levels
- **Elementary**: Grades 3-5
- **Intermediate**: Grades 6-8
- **Advanced**: Grades 9-10
- **Expert**: Grades 11-12+

---

## Troubleshooting

### Database Connection Error
```
Error: connect ECONNREFUSED 127.0.0.1:5432
```
**Solution:** Ensure PostgreSQL service is running.

### Tesseract Not Found (OCR)
```
TesseractNotFoundError: tesseract is not installed
```
**Solution:** Install Tesseract and update the path in `ml-service/.env`.

### Port Already in Use
```
Error: listen EADDRINUSE: address already in use :::5000
```
**Solution:** Kill the process using the port or change the port in `.env`.

### Python Module Not Found
```
ModuleNotFoundError: No module named 'flask'
```
**Solution:** Activate virtual environment and run `pip install -r requirements.txt`.

---

## License

MIT License

---

## Author

Computer Science Final Year Project
