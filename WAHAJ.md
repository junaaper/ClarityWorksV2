# ClarityWorks - Setup & Run Guide

## Prerequisites

Install the following software before proceeding:

| Software | Version | Download |
|----------|---------|----------|
| **Node.js** | v18+ | https://nodejs.org/ |
| **Python** | 3.9+ | https://www.python.org/downloads/ |
| **PostgreSQL** | 14+ | https://www.postgresql.org/download/ |
| **Tesseract OCR** | Latest | https://github.com/UB-Mannheim/tesseract/wiki |
| **Git** | Latest | https://git-scm.com/downloads |

> **Tesseract**: During installation, note the install path (default: `C:/Program Files/Tesseract-OCR/tesseract.exe`). You'll need it for the ML service `.env`.

---

## 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/clarityworksv2.git
cd clarityworksv2
```

---

## 2. Database Setup

Open a terminal or **pgAdmin** and run:

```sql
CREATE DATABASE clarityworks_db;
CREATE USER clarityworks_user WITH PASSWORD 'clarityworks_pass';
GRANT ALL PRIVILEGES ON DATABASE clarityworks_db TO clarityworks_user;
\c clarityworks_db
GRANT ALL ON SCHEMA public TO clarityworks_user;
```

> Tables are auto-created when the backend starts — no manual migration needed.

---

## 3. Environment Variables

Create a `.env` file in each of the three service directories:

### `backend/.env`

```env
PORT=5000
DATABASE_URL=postgresql://clarityworks_user:clarityworks_pass@localhost:5432/clarityworks_db
JWT_SECRET=change_this_to_a_long_random_secret
PYTHON_SERVICE_URL=http://localhost:5001
NODE_ENV=development
```

### `frontend/.env`

```env
VITE_API_URL=http://localhost:5000
VITE_PYTHON_API_URL=http://localhost:5001
```

### `ml-service/.env`

```env
FLASK_PORT=5001
FLASK_ENV=production
TESSERACT_PATH=C:/Program Files/Tesseract-OCR/tesseract.exe
GROQ_API_KEY=your_groq_api_key_here
```

> **GROQ_API_KEY**: Get a free API key from https://console.groq.com/. Required for text simplification validation and RAG answer generation. The app still works without it but those features will be limited.

---

## 4. Backend Setup (Node.js/Express)

```bash
cd backend
npm install
```

Start the backend (runs on **port 5000**):

```bash
npm run dev
```

---

## 5. ML Service Setup (Python/Flask)

```bash
cd ml-service
```

Create and activate a virtual environment:

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Download the spaCy English model:

```bash
python -m spacy download en_core_web_sm
```

Download NLTK WordNet data:

```bash
python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
```

### Train the ML Model (Optional but Recommended)

The app works without trained models (falls back to Flesch-Kincaid heuristic), but for accurate predictions:

```bash
python train_model.py
```

This trains 3 models (Random Forest, Gradient Boosting, XGBoost) on the CLEAR Corpus dataset and saves them to `trained_models/`.

### Start the ML Service (runs on **port 5001**):

```bash
python app.py
```

---

## 6. Frontend Setup (React/Vite)

```bash
cd frontend
npm install
```

Start the frontend (runs on **port 5173**):

```bash
npm run dev
```

---

## 7. Access the Application

Open your browser and go to:

```
http://localhost:5173
```

Register a new account and start analyzing text.

---

## Running All Three Services

You need **3 separate terminals** running simultaneously:

| Terminal | Directory | Command |
|----------|-----------|---------|
| 1 | `backend/` | `npm run dev` |
| 2 | `ml-service/` | `venv\Scripts\activate && python app.py` |
| 3 | `frontend/` | `npm run dev` |

---

## Creating an Admin User

By default all users are created with the `user` role. To make a user an admin, run this SQL:

```sql
UPDATE users SET role = 'admin' WHERE email = 'your_email@example.com';
```

---

## Troubleshooting

### torch DLL error on Windows
If you see a DLL error related to `thinc`/`torch`, this is already handled by `models/__init__.py` setting `THINC_NO_TORCH=1`. If it persists, edit `venv/Lib/site-packages/thinc/compat.py` and change `except ImportError:` to `except (ImportError, OSError):` in the torch import block.

### PostgreSQL connection refused
Make sure PostgreSQL is running and the credentials in `backend/.env` match your database setup.

### Tesseract not found
Ensure the `TESSERACT_PATH` in `ml-service/.env` points to your actual Tesseract installation path.

### textstat deprecation warnings
These are harmless `pkg_resources` warnings from the `textstat` library. They don't affect functionality.
