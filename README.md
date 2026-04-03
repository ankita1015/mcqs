# 🎓 AI MCQ Exam Generator — Groq Edition

A production-ready Python application that uploads a PDF, extracts its text, and generates adaptive multiple-choice questions using **Groq's Llama 3 70B** — then conducts a timed, interactive exam.

---

## 📁 Project Structure

```
MCQS/
├── backend/
│   ├── __init__.py
│   ├── main.py          # FastAPI REST API
│   ├── mcq_generator.py # Groq MCQ generation logic
│   └── pdf_parser.py    # PDF text extraction & chunking
├── frontend/
│   └── app.py           # Streamlit UI
├── venv/                # Virtual environment
├── .env.example         # Environment variable template
├── Procfile             # Render deployment config
├── requirements.txt
└── README.md
```

---

## 🚀 Local Setup & Running

### 1. Activate the virtual environment

```bash
cd /home/ankita/Documents/projects/MCQS
source venv/bin/activate
```

### 2. Configure your Groq API key

Get a **free** key at [console.groq.com/keys](https://console.groq.com/keys).

```bash
cp .env.example .env
# Edit .env and paste your GROQ_API_KEY
```

Or export directly:

```bash
export GROQ_API_KEY="gsk_..."
```

### 3. Run the backend (FastAPI)

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Run the frontend (Streamlit) — second terminal

```bash
streamlit run frontend/app.py
```

Visit **http://localhost:8501** in your browser.

---

## ☁️ Deployment

### Backend → Render (free tier)

1. Push repo to GitHub.
2. Go to [render.com](https://render.com) → **New Web Service** → connect your repo.
3. Build command: `pip install -r requirements.txt`
4. Start command comes from `Procfile` automatically.
5. Add environment variable `GROQ_API_KEY` in the Render dashboard.

> The `Procfile` already sets `--host 0.0.0.0 --port $PORT` for Render.

### Frontend → Streamlit Cloud

1. Push repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Set **Main file path**: `frontend/app.py`
4. Under **Secrets**, add:
   ```toml
   GROQ_API_KEY = "gsk_..."
   ```
5. Update `API_BASE_URL` in `frontend/app.py` to your Render backend URL:
   ```python
   API_BASE_URL = "https://your-app.onrender.com"
   ```

---

## 🔑 API Reference

| Method | Endpoint             | Description                    |
|--------|----------------------|--------------------------------|
| GET    | `/api/health`        | Health check                   |
| POST   | `/api/upload-pdf`    | Upload & parse a PDF           |
| POST   | `/api/generate-mcqs` | Generate MCQs from the PDF     |
| GET    | `/docs`              | Swagger interactive docs       |

### Upload PDF

```http
POST /api/upload-pdf
Content-Type: multipart/form-data

file: <your-pdf>
```

Response:
```json
{
  "session_id": "uuid",
  "filename": "textbook.pdf",
  "num_characters": 42000,
  "num_pages_estimated": 21,
  "message": "PDF processed successfully."
}
```

### Generate MCQs

```http
POST /api/generate-mcqs
Content-Type: application/json

{
  "session_id": "uuid",
  "num_questions": 10,
  "difficulty": "Medium",
  "api_key": "gsk_..."
}
```

Response:
```json
{
  "session_id": "uuid",
  "num_questions": 10,
  "difficulty": "Medium",
  "mcqs": [
    {
      "question": "What is ...?",
      "options": ["A. option1", "B. option2", "C. option3", "D. option4"],
      "correct_answer": "B",
      "explanation": "Because ..."
    }
  ]
}
```

---

## ✨ Feature Summary

| Feature | Detail |
|---|---|
| **AI** | Groq `llama3-70b-8192` via OpenAI-compatible SDK |
| **PDF Parsing** | pdfplumber (primary) + PyPDF2 (fallback) |
| **Chunking** | Distributes questions across document chunks |
| **JSON Validation** | Strict schema validation; per-MCQ normalisation |
| **Retry logic** | Exponential back-off on rate-limit / timeout errors |
| **Deduplication** | No repeated questions across chunks |
| **Difficulty** | Easy / Medium / Hard with distinct prompts |
| **Timer** | 30 sec/question countdown, auto-submit on expiry |
| **Navigation** | Prev / Next with dot progress indicators |
| **Results** | Score ring, stat cards, per-question review + explanations |
| **Dark Theme** | Glassmorphism UI with Inter font |
| **CORS** | `allow_origins=["*"]` for cross-origin frontend calls |
| **Deployment** | Render (backend) + Streamlit Cloud (frontend) |

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | **Required.** Your Groq secret key (`gsk_…`). |
| `GROQ_MODEL` | `llama3-70b-8192` | Groq model to use. |

---

## ⚠️ Notes

- Extracted text is stored **in memory**. For multi-process / persistent deployments replace `_text_store` in `main.py` with Redis or a database.
- Image-only / scanned PDFs yield no text — pre-process with OCR (`pytesseract`) if needed.
- Keep `GROQ_API_KEY` out of version control; add `.env` to `.gitignore`.
