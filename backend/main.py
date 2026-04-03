"""
main.py
-------
FastAPI backend for the MCQ Exam Generator.

Endpoints:
  POST /api/upload-pdf   – Upload and parse a PDF; returns extracted text metadata.
  POST /api/generate-mcqs – Generate MCQs from previously uploaded text.
  GET  /api/health        – Health-check endpoint.
"""

import logging
import os
import sys
import uuid
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Ensure the backend package is importable when running from the project root
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from mcq_generator import generate_mcqs
from pdf_parser import extract_text_from_pdf

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & in-memory storage
# ---------------------------------------------------------------------------

# Maximum PDF size accepted (20 MB)
MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024

# Simple in-memory store: session_id → extracted text
# In production you would replace this with Redis, a DB, or signed JWTs.
_text_store: Dict[str, str] = {}

ALLOWED_DIFFICULTIES = {"Easy", "Medium", "Hard"}

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MCQ Exam Generator API",
    description="Upload a PDF and generate AI-powered multiple-choice questions.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow all origins for local development; tighten in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    session_id: str
    filename: str
    num_characters: int
    num_pages_estimated: int
    message: str


class MCQRequest(BaseModel):
    session_id: str = Field(..., description="Session ID returned by /api/upload-pdf")
    num_questions: int = Field(..., ge=1, le=100, description="Number of MCQs to generate (1–100)")
    difficulty: str = Field(..., description="Difficulty: Easy | Medium | Hard")
    api_key: Optional[str] = Field(None, description="Groq API key (optional if GROQ_API_KEY env var is set)")

    @validator("difficulty")
    def validate_difficulty(cls, v: str) -> str:
        if v not in ALLOWED_DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {sorted(ALLOWED_DIFFICULTIES)}")
        return v


class MCQItem(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    explanation: str


class MCQResponse(BaseModel):
    session_id: str
    num_questions: int
    difficulty: str
    mcqs: List[MCQItem]


class HealthResponse(BaseModel):
    status: str
    version: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health", response_model=HealthResponse, tags=["Utility"])
async def health_check() -> HealthResponse:
    """Returns service health status."""
    return HealthResponse(status="ok", version=app.version)


@app.post(
    "/api/upload-pdf",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["PDF"],
)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    """
    Upload a PDF file and extract its text content.

    Returns a `session_id` which must be passed to `/api/generate-mcqs`.
    """
    # Validate MIME type
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        # Some browsers/clients send octet-stream; also accept it and rely on extension.
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only PDF files are accepted.",
            )

    # Read and size-check
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(file_bytes) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"PDF exceeds maximum allowed size of {MAX_PDF_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    # Extract text
    try:
        text = extract_text_from_pdf(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    # Store and return
    session_id = str(uuid.uuid4())
    _text_store[session_id] = text

    estimated_pages = max(1, len(text) // 2000)  # rough heuristic
    logger.info(
        f"PDF uploaded: '{file.filename}' | session={session_id} | "
        f"chars={len(text)} | ~{estimated_pages} pages"
    )

    return UploadResponse(
        session_id=session_id,
        filename=file.filename or "unknown.pdf",
        num_characters=len(text),
        num_pages_estimated=estimated_pages,
        message="PDF processed successfully. Use the session_id to generate MCQs.",
    )


@app.post(
    "/api/generate-mcqs",
    response_model=MCQResponse,
    tags=["MCQ"],
)
async def generate_mcqs_endpoint(request: MCQRequest) -> MCQResponse:
    """
    Generate MCQs from a previously uploaded PDF.

    Requires the `session_id` returned by `/api/upload-pdf`.
    """
    # Retrieve stored text
    text = _text_store.get(request.session_id)
    if text is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Session '{request.session_id}' not found. "
                "Please upload a PDF first via /api/upload-pdf."
            ),
        )

    logger.info(
        f"Generating {request.num_questions} '{request.difficulty}' MCQs | "
        f"session={request.session_id}"
    )

    try:
        raw_mcqs: List[Dict[str, Any]] = generate_mcqs(
            text=text,
            num_questions=request.num_questions,
            difficulty=request.difficulty,
            api_key=request.api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    mcq_items = [MCQItem(**m) for m in raw_mcqs]

    logger.info(
        f"Successfully generated {len(mcq_items)} MCQs | session={request.session_id}"
    )

    return MCQResponse(
        session_id=request.session_id,
        num_questions=len(mcq_items),
        difficulty=request.difficulty,
        mcqs=mcq_items,
    )
