"""
mcq_generator.py
----------------
Generates MCQs from text using the Groq API (via the OpenAI-compatible SDK).

Features:
  - Handles large documents via text chunking.
  - Distributes MCQ generation proportionally across chunks.
  - Retries on transient failures.
  - Strict JSON prompt-level validation (Groq doesn't support json_object mode).
  - Deduplicates questions to prevent repetition.
"""

import json
import logging
import os
import random
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI, APIError, APITimeoutError, RateLimitError

from pdf_parser import chunk_text, get_representative_chunks

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Groq model — change via GROQ_MODEL env var if needed.
# llama3-70b-8192 was decommissioned; use llama-3.3-70b-versatile instead.
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Groq API base URL (OpenAI-compatible)
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Tokens budget per API call
MAX_TOKENS = 4096

# Number of retry attempts on transient errors
MAX_RETRIES = 3

# Seconds to wait before each retry (exponential backoff multiplier)
RETRY_BACKOFF_BASE = 2

# Hard cap: never request more than this many MCQs in one prompt
MAX_MCQS_PER_CHUNK = 15

# Difficulty → descriptive instruction mapping
DIFFICULTY_PROMPTS: Dict[str, str] = {
    "Easy": (
        "Generate straightforward questions that test basic recall and simple comprehension. "
        "Options should be clearly distinguishable."
    ),
    "Medium": (
        "Generate questions that require understanding of concepts and some interpretation. "
        "All distractors should be plausible."
    ),
    "Hard": (
        "Generate challenging questions that require deep analysis, inference, or synthesis. "
        "All four options should seem reasonable to a casual reader."
    ),
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_mcqs(
    text: str,
    num_questions: int,
    difficulty: str,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Generate MCQs from the provided text.

    Args:
        text:          Extracted document text.
        num_questions: Number of MCQs to generate.
        difficulty:    One of "Easy", "Medium", "Hard".
        api_key:       Groq API key (falls back to GROQ_API_KEY env var).

    Returns:
        List of MCQ dicts, each with keys:
            question, options (list[str]), correct_answer (str), explanation (str).

    Raises:
        ValueError: If difficulty is invalid, no questions could be generated, etc.
        RuntimeError: On unrecoverable API errors.
    """
    if difficulty not in DIFFICULTY_PROMPTS:
        raise ValueError(
            f"Invalid difficulty '{difficulty}'. Choose from: {list(DIFFICULTY_PROMPTS.keys())}"
        )

    if num_questions < 1:
        raise ValueError("num_questions must be at least 1.")

    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError(
            "Groq API key not found. Set the GROQ_API_KEY environment variable "
            "or pass api_key to the function."
        )

    # Use the OpenAI SDK pointed at Groq's OpenAI-compatible endpoint
    client = OpenAI(api_key=key, base_url=GROQ_BASE_URL)

    # Decide how many chunks and how many questions per chunk
    chunks = _select_chunks(text, num_questions)
    per_chunk_counts = _distribute_questions(num_questions, len(chunks))

    all_mcqs: List[Dict[str, Any]] = []
    seen_questions: set = set()

    for idx, (chunk, count) in enumerate(zip(chunks, per_chunk_counts)):
        logger.info(f"Generating {count} MCQs from chunk {idx + 1}/{len(chunks)} …")
        try:
            mcqs = _generate_chunk_mcqs(client, chunk, count, difficulty)
        except Exception as exc:
            logger.error(f"Failed to generate MCQs for chunk {idx + 1}: {exc}")
            continue

        # Deduplicate
        for mcq in mcqs:
            q_key = mcq["question"].lower().strip()
            if q_key not in seen_questions:
                seen_questions.add(q_key)
                all_mcqs.append(mcq)

    if not all_mcqs:
        raise RuntimeError(
            "Failed to generate any MCQs. "
            "Please check your API key, PDF content, and retry."
        )

    # Randomize order
    random.shuffle(all_mcqs)

    # Trim or pad to exact count
    return all_mcqs[:num_questions]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _select_chunks(text: str, num_questions: int) -> List[str]:
    """Return text chunks appropriate for the number of questions requested."""
    # More questions → more chunks to cover more of the document
    desired_chunks = max(1, min(num_questions // 5 + 1, 10))
    return get_representative_chunks(text, num_chunks=desired_chunks)


def _distribute_questions(total: int, num_chunks: int) -> List[int]:
    """Distribute `total` questions across `num_chunks` as evenly as possible."""
    base = total // num_chunks
    remainder = total % num_chunks
    distribution = [base] * num_chunks
    for i in range(remainder):
        distribution[i] += 1
    # Clamp each chunk to the per-chunk maximum
    return [min(c, MAX_MCQS_PER_CHUNK) for c in distribution]


def _generate_chunk_mcqs(
    client: OpenAI,
    chunk: str,
    count: int,
    difficulty: str,
) -> List[Dict[str, Any]]:
    """
    Call the Groq API for a single text chunk and return validated MCQs.
    Retries up to MAX_RETRIES times on transient errors.
    """
    system_prompt = _build_system_prompt(difficulty)
    user_prompt = _build_user_prompt(chunk, count, difficulty)

    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # NOTE: Groq does not support response_format="json_object" via the
            # OpenAI SDK for all models, so we enforce JSON through the prompt.
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=MAX_TOKENS,
                temperature=0.7,
            )

            raw_content = response.choices[0].message.content
            return _parse_and_validate(raw_content, count)

        except (APITimeoutError, RateLimitError) as exc:
            wait = RETRY_BACKOFF_BASE ** attempt
            logger.warning(
                f"Attempt {attempt}/{MAX_RETRIES} failed ({exc}). "
                f"Retrying in {wait}s …"
            )
            time.sleep(wait)
            last_error = exc

        except APIError as exc:
            # Treat 4xx as non-retryable only if it's an auth or model error;
            # otherwise treat as transient and retry.
            status = getattr(exc, 'status_code', None)
            if status in (401, 403):
                raise RuntimeError(f"Groq authentication error: {exc}") from exc
            logger.warning(
                f"Attempt {attempt}/{MAX_RETRIES} Groq API error ({status}): {exc}. "
                f"Retrying in {RETRY_BACKOFF_BASE ** attempt}s …"
            )
            time.sleep(RETRY_BACKOFF_BASE ** attempt)
            last_error = exc

        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"Attempt {attempt}/{MAX_RETRIES}: JSON parse error – {exc}")
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(1)

    raise RuntimeError(
        f"All {MAX_RETRIES} attempts failed. Last error: {last_error}"
    )


def _build_system_prompt(difficulty: str) -> str:
    return (
        "You are an expert educator and MPSC (Maharashtra Public Service Commission) exam paper setter. "
        "Your task is to create high-quality MCQs strictly based on the provided text, "
        "aligned with MPSC exam standards including Prelims and Mains objective patterns. "

        f"Difficulty: {difficulty}. {DIFFICULTY_PROMPTS[difficulty]} "

        "MPSC Question Design Guidelines:\n"
        "- Focus on conceptual clarity, factual accuracy, and analytical thinking.\n"
        "- Include tricky and close options to test deep understanding.\n"
        "- Avoid direct copy-paste; reframe questions in exam style.\n"
        "- Cover definitions, facts, cause-effect, and application-based questions.\n"
        "- Mix easy, moderate, and difficult questions as per difficulty setting.\n"
        "- Use exam-oriented language similar to competitive exams.\n"
        "- Avoid ambiguity; only one option must be clearly correct.\n"

        "IMPORTANT: You MUST respond with raw JSON only — no markdown fences, "
        "no backticks, no preamble, no trailing text. "
        "Start your response with {{ and end with }}. "

        "The JSON must follow this exact schema:\n"
        '{"mcqs": [{"question": "string", "options": ["A. text", "B. text", "C. text", "D. text"], '
        '"correct_answer": "A", "explanation": "string"}]}\n'

        "Rules:\n"
        "- Each question must have exactly 4 options labeled A, B, C, D.\n"
        "- correct_answer must be exactly one letter: A, B, C, or D.\n"
        "- All questions must be based solely on the given text.\n"
        "- Explanations must reference the source text.\n"
        "- No duplicate questions.\n"
        "- Ensure questions resemble real competitive exam patterns like MPSC.\n"
    )


def _build_user_prompt(chunk: str, count: int, difficulty: str) -> str:
    return (
        f"Generate exactly {count} {difficulty}-difficulty MCQs based on the following text:\n\n"
        f"---\n{chunk}\n---\n\n"
        f"Return ONLY a JSON object with a 'mcqs' array containing {count} question objects."
    )


def _strip_markdown_fences(text: str) -> str:
    """
    Remove markdown code fences that LLMs sometimes add despite being told not to.

    Handles variants like:
        ```json { ... } ```
        ``` { ... } ```
        ```\n{ ... }\n```
    """
    text = text.strip()
    # Remove opening fence (```json or ```)
    if text.startswith("```"):
        # Drop the first line (the fence + optional language tag)
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        else:
            text = text[3:]  # just strip the backticks if no newline
    # Remove closing fence
    if text.endswith("```"):
        text = text[: text.rfind("```")].rstrip()
    return text.strip()


def _parse_and_validate(raw_content: str, expected_count: int) -> List[Dict[str, Any]]:
    """
    Parse the raw API response and validate each MCQ against the expected schema.

    Args:
        raw_content:    Raw string from the API.
        expected_count: Number of MCQs expected (used for logging, not enforced strictly).

    Returns:
        List of validated MCQ dicts.

    Raises:
        ValueError: If the response cannot be parsed or contains no valid MCQs.
    """
    cleaned = _strip_markdown_fences(raw_content)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"API returned invalid JSON: {exc}\nRaw (first 500 chars): {cleaned[:500]}"
        ) from exc

    # Support both {"mcqs": [...]} and a bare list
    if isinstance(data, list):
        mcq_list = data
    elif isinstance(data, dict):
        # Try common keys
        for key in ("mcqs", "questions", "items", "data"):
            if key in data and isinstance(data[key], list):
                mcq_list = data[key]
                break
        else:
            raise ValueError(
                f"Unexpected JSON structure. Keys found: {list(data.keys())}"
            )
    else:
        raise ValueError("API response is neither a list nor an object.")

    valid_mcqs: List[Dict[str, Any]] = []
    for i, item in enumerate(mcq_list):
        try:
            validated = _validate_mcq(item)
            valid_mcqs.append(validated)
        except ValueError as exc:
            logger.warning(f"Skipping MCQ {i + 1} due to validation error: {exc}")

    if not valid_mcqs:
        raise ValueError("No valid MCQs found in the API response.")

    logger.info(
        f"Validated {len(valid_mcqs)}/{expected_count} MCQs from API response."
    )
    return valid_mcqs


def _validate_mcq(item: Any) -> Dict[str, Any]:
    """
    Validate and normalise a single MCQ dict.

    Raises:
        ValueError: On any schema violation.
    """
    if not isinstance(item, dict):
        raise ValueError(f"MCQ must be a dict, got {type(item).__name__}.")

    # --- question ---
    question = item.get("question", "").strip()
    if not question:
        raise ValueError("Missing or empty 'question'.")

    # --- options ---
    options = item.get("options", [])
    if not isinstance(options, list) or len(options) != 4:
        raise ValueError(
            f"'options' must be a list of exactly 4 items, got {len(options) if isinstance(options, list) else type(options).__name__}."
        )
    options = [str(o).strip() for o in options]
    for opt in options:
        if not opt:
            raise ValueError("Option text must not be empty.")

    # Ensure options are prefixed A–D
    labels = ["A", "B", "C", "D"]
    normalised_options: List[str] = []
    for label, opt in zip(labels, options):
        # Strip existing prefix if already present (e.g. "A. foo" or "A) foo")
        text = opt
        if len(opt) >= 2 and opt[0].upper() in labels and opt[1] in (".", ")", ":"):
            text = opt[2:].strip()
        normalised_options.append(f"{label}. {text}")

    # --- correct_answer ---
    correct_answer = str(item.get("correct_answer", "")).strip().upper()
    # Accept "A.", "A)", "A. text", etc.
    if correct_answer and correct_answer[0] in labels:
        correct_answer = correct_answer[0]
    if correct_answer not in labels:
        raise ValueError(
            f"'correct_answer' must be A, B, C, or D. Got '{correct_answer}'."
        )

    # --- explanation ---
    explanation = str(item.get("explanation", "")).strip()
    if not explanation:
        explanation = "No explanation provided."

    return {
        "question": question,
        "options": normalised_options,
        "correct_answer": correct_answer,
        "explanation": explanation,
    }
