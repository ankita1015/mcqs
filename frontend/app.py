"""
app.py
------
Streamlit frontend for the MCQ Exam Generator.

Features:
  - PDF upload via sidebar
  - Difficulty & question count controls
  - One-question-at-a-time exam with navigation
  - Countdown timer with auto-submit
  - Progress bar & sticky header
  - Detailed results page with explanations
"""

import time
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# 
API_BASE_URL = "https://mcqs-ehex.onrender.com"
# API_BASE_URL = "http://localhost:8000"

# Seconds allocated per question
SECONDS_PER_QUESTION = 30

# ---------------------------------------------------------------------------
# Page config — MUST be the first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI MCQ Exam Generator",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — premium dark theme
# ---------------------------------------------------------------------------

st.markdown(
    """
<style>
/* ── Google Font ─────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Root variables ─────────────────────────────────────────────── */
:root {
    --bg-primary:    #0d0f1a;
    --bg-secondary:  #161827;
    --bg-card:       #1e2235;
    --bg-card-hover: #252842;
    --accent:        #6c63ff;
    --accent-light:  #8b85ff;
    --accent-glow:   rgba(108, 99, 255, 0.25);
    --success:       #22c55e;
    --danger:        #ef4444;
    --warning:       #f59e0b;
    --text-primary:  #f1f3ff;
    --text-secondary:#a8adc8;
    --border:        rgba(108, 99, 255, 0.2);
    --radius:        16px;
    --radius-sm:     10px;
    --shadow:        0 8px 32px rgba(0, 0, 0, 0.4);
}

/* ── Global reset ───────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
    overflow-x: hidden !important;
}
[data-testid="stAppViewContainer"] {
    overflow-x: hidden !important;
}

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] .stButton > button {
    width: 100%;
}

/* ── Buttons ─────────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, var(--accent), var(--accent-light));
    color: #fff !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    padding: 0.65rem 1.5rem !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 4px 15px var(--accent-glow) !important;
    cursor: pointer !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px var(--accent-glow) !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
}

/* ── Cards ───────────────────────────────────────────────────────── */
.mcq-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
    box-shadow: var(--shadow);
    transition: box-shadow 0.3s ease;
    animation: slideIn 0.4s ease;
}
.mcq-card:hover {
    box-shadow: 0 12px 40px rgba(108, 99, 255, 0.15);
}

@keyframes slideIn {
    from { opacity: 0; transform: translateY(20px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ── Sticky header ───────────────────────────────────────────────── */
.sticky-header {
    position: sticky;
    top: 0;
    z-index: 999;
    background: rgba(13, 15, 26, 0.92);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    padding: 0.75rem 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-radius: 0 0 var(--radius) var(--radius);
    margin-bottom: 1.5rem;
}

/* ── Timer badge ─────────────────────────────────────────────────── */
.timer-badge {
    background: linear-gradient(135deg, #ff4757, #ff6b81);
    color: #fff;
    font-size: 1.1rem;
    font-weight: 700;
    padding: 0.4rem 1.1rem;
    border-radius: 50px;
    box-shadow: 0 4px 15px rgba(255, 71, 87, 0.4);
    display: inline-block;
    letter-spacing: 0.5px;
}
.timer-badge.safe {
    background: linear-gradient(135deg, var(--accent), var(--accent-light));
    box-shadow: 0 4px 15px var(--accent-glow);
}
.timer-badge.warning {
    background: linear-gradient(135deg, #f59e0b, #fbbf24);
    box-shadow: 0 4px 15px rgba(245, 158, 11, 0.4);
}

/* ── Progress bar override ───────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, var(--accent), var(--accent-light)) !important;
    border-radius: 50px !important;
}
[data-testid="stProgressBar"] > div {
    background: var(--bg-card) !important;
    border-radius: 50px !important;
}

/* ── Radio buttons ───────────────────────────────────────────────── */
/* ── Radio buttons (Options) ─────────────────────────────────────── */
[data-testid="stRadio"] > div {
    gap: 0.75rem !important;
}
[data-testid="stRadio"] label {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    padding: 0.85rem 1.25rem !important;
    margin-bottom: 0 !important;
    display: flex !important;
    align-items: center !important;
    min-height: 3.5rem !important; /* Uniform height for all options */
    cursor: pointer !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2) !important;
}
[data-testid="stRadio"] label:hover {
    background: var(--bg-card-hover) !important;
    border-color: var(--accent) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 12px rgba(108, 99, 255, 0.2) !important;
}
/* Selected state highlight using :has if supported, otherwise focus-within */
[data-testid="stRadio"] label:has(input:checked),
[data-testid="stRadio"] label:focus-within {
    background: rgba(108, 99, 255, 0.12) !important;
    border-color: var(--accent) !important;
    box-shadow: 0 0 20px var(--accent-glow) !important;
    border-width: 2px !important;
}
[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {
    color: var(--text-primary) !important;
    font-size: 1.05rem !important;
    font-weight: 500 !important;
    margin: 0 !important;
}

/* ── Selectbox & number input ─────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stNumberInput"] input {
    background: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
}

/* ── File uploader ───────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    background: var(--bg-card) !important;
    border: 2px dashed var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 1rem !important;
    transition: border-color 0.3s ease !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: var(--accent) !important;
}

/* ── Result cards ─────────────────────────────────────────────────── */
.result-correct {
    border-left: 4px solid var(--success) !important;
}
.result-wrong {
    border-left: 4px solid var(--danger) !important;
}
.answer-pill {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 50px;
    font-size: 0.82rem;
    font-weight: 600;
}
.pill-correct { background: rgba(34, 197, 94, 0.15); color: var(--success); border: 1px solid rgba(34, 197, 94, 0.3); }
.pill-wrong   { background: rgba(239, 68, 68, 0.15);  color: var(--danger);  border: 1px solid rgba(239, 68, 68, 0.3); }
.pill-neutral { background: rgba(108, 99, 255, 0.15); color: var(--accent-light); border: 1px solid var(--border); }

/* ── Score circle ─────────────────────────────────────────────────── */
.score-circle {
    width: 160px;
    height: 160px;
    border-radius: 50%;
    border: 6px solid var(--accent);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    margin: 0 auto 1.5rem;
    background: radial-gradient(circle at center, var(--accent-glow), transparent 70%);
    box-shadow: 0 0 40px var(--accent-glow);
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { box-shadow: 0 0 40px var(--accent-glow); }
    50%       { box-shadow: 0 0 60px rgba(108, 99, 255, 0.4); }
}
.score-pct   { font-size: 2.2rem; font-weight: 800; color: var(--accent-light); line-height: 1; }
.score-label { font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px; }

/* ── Stat boxes ───────────────────────────────────────────────────── */
.stats-container {
    display: flex;
    gap: 0.5rem;
    justify-content: space-between;
    margin-top: 0.5rem;
}
.stat-box {
    flex: 1;
    background: var(--bg-secondary);
    border-radius: var(--radius-sm);
    padding: 0.75rem 0.5rem;
    text-align: center;
    border: 1px solid var(--border);
    transition: transform 0.2s ease;
}
.stat-box:hover {
    transform: translateY(-2px);
    border-color: var(--accent);
}
.stat-val { font-size: 1.5rem; font-weight: 800; line-height: 1.2; }
.stat-lbl { font-size: 0.65rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }

/* ── Typography helpers ───────────────────────────────────────────── */
h1, h2, h3 { color: var(--text-primary) !important; }
.subtitle   { color: var(--text-secondary); font-size: 0.9rem; }

/* ── Divider ─────────────────────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 1.5rem 0 !important;
}

/* ── Alerts / info boxes ─────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: var(--radius-sm) !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

/* ── Mobile Responsiveness ────────────────────────────────────────── */
@media (max-width: 768px) {
    /* Reduce card padding */
    .mcq-card {
        padding: 1.25rem 1.5rem !important;
        margin-bottom: 1rem !important;
    }
    
    /* Compact sticky header */
    .sticky-header {
        padding: 0.5rem 1rem !important;
        border-radius: 0 !important;
        margin-bottom: 1rem !important;
    }
    
    .sticky-header div:first-child span:first-child {
        font-size: 0.9rem !important;
        display: -webkit-box !important;
        -webkit-line-clamp: 1;
        -webkit-box-orient: vertical;
        overflow: hidden;
        max-width: 160px;
    }
    
    .subtitle {
        font-size: 0.75rem !important;
        margin-left: 0 !important;
    }
    
    .timer-badge {
        font-size: 0.9rem !important;
        padding: 0.25rem 0.75rem !important;
    }

    /* Score circle scaling */
    .score-circle {
        width: 120px !important;
        height: 120px !important;
    }
    .score-pct { font-size: 1.8rem !important; }

    /* Fix for buttons stacking on mobile */
    [data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 0.5rem !important;
    }
    [data-testid="column"] {
        flex: 1 1 0% !important;
        min-width: 0 !important;
    }
    
    .stButton > button {
        padding: 0.5rem 0.75rem !important;
        font-size: 0.85rem !important;
        width: 100% !important;
    }

    /* Prevent horizontal scroll while keeping columns horizontal */
    [data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: wrap !important; /* Allow wrapping if needed */
        gap: 0.25rem !important;
        width: 100% !important;
    }
    
    [data-testid="column"] {
        flex: 1 1 0% !important;
        min-width: 100px !important; /* Minimum width for buttons */
        padding: 0 !important;
    }

    /* Force stats to stack vertically on mobile for better visibility */
    .stats-container {
        flex-direction: column !important;
        gap: 0.75rem !important;
        margin-top: 1.5rem !important;
    }
    .stat-box {
        padding: 1rem !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        text-align: left !important;
    }
    .stat-val { font-size: 1.5rem !important; margin-left: 10px; }
    .stat-lbl { font-size: 0.8rem !important; margin: 0; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------


def _init_state() -> None:
    """Initialise all session state keys with default values."""
    defaults: Dict[str, Any] = {
        "phase": "setup",           # setup | exam | results
        "session_id": None,
        "mcqs": [],
        "current_idx": 0,
        "answers": {},              # {idx: selected_option_letter}
        "exam_start_time": None,
        "total_seconds": 0,
        "submitted": False,
        "api_key_input": "",
        "num_questions": 10,
        "difficulty": "Medium",
        "require_answer": False,
        "pdf_name": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_state()

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def _api_upload(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    response = requests.post(
        f"{API_BASE_URL}/api/upload-pdf",
        files={"file": (filename, file_bytes, "application/pdf")},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def _api_generate(
    session_id: str,
    num_questions: int,
    difficulty: str,
    api_key: Optional[str],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "session_id": session_id,
        "num_questions": num_questions,
        "difficulty": difficulty,
    }
    if api_key:
        payload["api_key"] = api_key
    response = requests.post(
        f"{API_BASE_URL}/api/generate-mcqs",
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <div style='text-align:center; padding: 1.5rem 0 0.5rem;'>
                <span style='font-size:2.8rem;'>🎓</span>
                <h2 style='margin:0; font-size:1.4rem; font-weight:800;'>MCQ Portal</h2>
                <p style='color:var(--text-secondary); font-size:0.8rem; margin:0;'>MPSC Exam Engine</p>
            </div>
            <hr/>
            """,
            unsafe_allow_html=True,
        )

        if st.session_state.phase != "setup":
            st.markdown("### 🎯 Current Exam")
            st.write(f"**PDF**: {st.session_state.pdf_name}")
            st.write(f"**Difficulty**: {st.session_state.difficulty}")
            st.markdown("<br/>", unsafe_allow_html=True)
            if st.button("❌ Quit Exam", use_container_width=True):
                _reset_exam()
                st.rerun()
            return

        # --- PDF Upload ---
        st.markdown("**📄 Upload PDF**")
        uploaded_file = st.file_uploader(
            "Drop your PDF here",
            type=["pdf"],
            label_visibility="collapsed",
            key="pdf_uploader",
        )

        st.markdown("<hr/>", unsafe_allow_html=True)

        # --- OpenAI API Key ---
        st.markdown("**🔑 Groq API Key**")
        api_key = st.text_input(
            "API Key",
            type="password",
            placeholder="gsk_…  (or set GROQ_API_KEY env var)",
            label_visibility="collapsed",
            key="api_key_input",
        )

        st.markdown("<hr/>", unsafe_allow_html=True)

        # --- Exam Settings ---
        st.markdown("**⚙️ Exam Settings**")

        difficulty = st.selectbox(
            "Difficulty",
            options=["Easy", "Medium", "Hard"],
            index=["Easy", "Medium", "Hard"].index(st.session_state.difficulty),
            key="difficulty_select",
        )

        num_questions = st.number_input(
            "Number of Questions",
            min_value=1,
            max_value=100,
            value=st.session_state.num_questions,
            step=1,
            key="num_questions_input",
        )

        require_answer = st.checkbox(
            "Require answer before next",
            value=st.session_state.require_answer,
            key="require_answer_check",
        )

        # Persist settings
        st.session_state.difficulty = difficulty
        st.session_state.num_questions = int(num_questions)
        st.session_state.require_answer = require_answer

        st.markdown("<hr/>", unsafe_allow_html=True)

        # --- Start Button ---
        start_disabled = uploaded_file is None or st.session_state.phase == "exam"
        if st.button("🚀 Start Exam", disabled=start_disabled, use_container_width=True):
            _handle_start(uploaded_file, api_key)

        # --- Restart Button ---
        if st.session_state.phase in ("exam", "results"):
            if st.button("🔄 Restart", use_container_width=True):
                _reset_exam()
                st.rerun()


# ---------------------------------------------------------------------------
# Start exam logic
# ---------------------------------------------------------------------------


def _handle_start(uploaded_file: Any, api_key: str) -> None:
    if uploaded_file is None:
        st.sidebar.error("Please upload a PDF file first.")
        return

    with st.spinner("📖 Parsing PDF…"):
        try:
            upload_resp = _api_upload(
                uploaded_file.getvalue(), uploaded_file.name
            )
        except requests.HTTPError as exc:
            detail = exc.response.json().get("detail", str(exc))
            st.sidebar.error(f"Upload failed: {detail}")
            return
        except requests.ConnectionError:
            st.sidebar.error(
                "Cannot reach the backend. "
                "Make sure the FastAPI server is running on port 8000."
            )
            return

    session_id = upload_resp["session_id"]
    st.session_state.pdf_name = upload_resp["filename"]

    with st.spinner(f"🤖 Generating {st.session_state.num_questions} MCQs…"):
        try:
            gen_resp = _api_generate(
                session_id=session_id,
                num_questions=st.session_state.num_questions,
                difficulty=st.session_state.difficulty,
                api_key=api_key or None,
            )
        except requests.HTTPError as exc:
            detail = exc.response.json().get("detail", str(exc))
            st.sidebar.error(f"Generation failed: {detail}")
            return

    st.session_state.session_id = session_id
    st.session_state.mcqs = gen_resp["mcqs"]
    st.session_state.current_idx = 0
    st.session_state.answers = {}
    st.session_state.submitted = False
    st.session_state.exam_start_time = time.time()
    st.session_state.total_seconds = (
        len(st.session_state.mcqs) * SECONDS_PER_QUESTION
    )
    st.session_state.phase = "exam"
    st.rerun()


def _reset_exam() -> None:
    keys_to_clear = [
        "phase", "session_id", "mcqs", "current_idx", "answers",
        "exam_start_time", "total_seconds", "submitted", "pdf_name",
    ]
    for k in keys_to_clear:
        if k in st.session_state:
            del st.session_state[k]
    _init_state()


# ---------------------------------------------------------------------------
# Setup / landing page
# ---------------------------------------------------------------------------


def render_setup_page() -> None:
    st.markdown(
        """
        <div style='text-align:center; padding: 3rem 1rem 1rem;'>
            <div style='font-size:4rem; margin-bottom:0.5rem;'>🎓</div>
            <h1 style='font-size:2.8rem; font-weight:800; margin:0;
                background: linear-gradient(135deg, #6c63ff, #a78bfa);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
                AI MCQ Exam Generator
            </h1>
            <p style='color:var(--text-secondary); font-size:1.1rem; margin-top:0.75rem;'>
                Upload any PDF → Set your difficulty → Take an AI-generated exam powered by Groq.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<br/>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    features = [
        ("📄", "Smart PDF Parsing", "Handles complex layouts, large files, and multi-page documents."),
                ("🤖", "AI-Powered MCQs", "Questions generated by Llama 3 70B via Groq — fast, contextual & varied."),
        ("⏱️", "Timed Exam Mode", "Countdown timer with auto-submit keeps the pressure on."),
    ]
    for col, (icon, title, desc) in zip([c1, c2, c3], features):
        with col:
            st.markdown(
                f"""
                <div class='mcq-card' style='text-align:center;'>
                    <div style='font-size:2rem; margin-bottom:0.5rem;'>{icon}</div>
                    <h3 style='margin:0; font-size:1rem; font-weight:700;'>{title}</h3>
                    <p style='color:var(--text-secondary); font-size:0.85rem; margin-top:0.4rem;'>{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br/>", unsafe_allow_html=True)
    st.info(
        "👈 **Get started:** Upload a PDF and configure your exam in the sidebar, "
        "then click **Start Exam**."
    )


# ---------------------------------------------------------------------------
# Exam page
# ---------------------------------------------------------------------------


def render_exam_page() -> None:
    mcqs: List[Dict[str, Any]] = st.session_state.mcqs
    idx: int = st.session_state.current_idx
    total: int = len(mcqs)

    # ── Compute remaining time ──────────────────────────────────────────────
    elapsed = time.time() - st.session_state.exam_start_time
    remaining = max(0, st.session_state.total_seconds - elapsed)
    minutes, seconds = divmod(int(remaining), 60)

    # ── Auto-submit when timer hits 0 ──────────────────────────────────────
    if remaining <= 0 and not st.session_state.submitted:
        st.session_state.phase = "results"
        st.session_state.submitted = True
        st.rerun()

    # ── Timer colour ────────────────────────────────────────────────────────
    pct_remaining = remaining / max(1, st.session_state.total_seconds)
    timer_cls = "safe" if pct_remaining > 0.5 else ("warning" if pct_remaining > 0.2 else "")

    # ── Sticky header (Integrated Progress) ─────────────────────────────────
    answered_count = len(st.session_state.answers)
    progress = answered_count / total
    st.markdown(
        f"""
        <div class='sticky-header'>
            <div style='flex: 1;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;'>
                    <span style='font-weight:700; font-size:0.95rem; display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 200px;'>
                        📝 {st.session_state.pdf_name}
                    </span>
                    <div class='timer-badge {timer_cls}'>
                        ⏱ {minutes:02d}:{seconds:02d}
                    </div>
                </div>
                <div class='subtitle' style='font-size:0.75rem; margin-bottom: 6px;'>
                    Question {idx + 1} of {total} · {st.session_state.difficulty}
                </div>
                <div style='width: 100%; height: 4px; background: var(--bg-secondary); border-radius: 2px; overflow: hidden;'>
                    <div style='width: {progress*100}%; height: 100%; background: var(--accent); transition: width 0.3s ease;'></div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<br/>", unsafe_allow_html=True)

    # ── Question card ───────────────────────────────────────────────────────
    mcq = mcqs[idx]
    st.markdown(
        f"""
        <div class='mcq-card'>
            <div style='display: flex; justify-content: space-between; margin-bottom: 0.75rem;'>
                <span class='pill-neutral answer-pill' style='font-size: 0.7rem;'>QUESTION {idx + 1}</span>
                <span style='opacity: 0.4; font-size: 0.8rem;'>{idx + 1} / {total}</span>
            </div>
            <h2 style='font-size:1.15rem; font-weight:600; line-height:1.5; margin:0;'>
                {mcq["question"]}
            </h2>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # ── Options ─────────────────────────────────────────────────────────────
    options: List[str] = mcq["options"]
    option_letters = [opt.split(".")[0].strip() for opt in options]

    current_answer = st.session_state.answers.get(idx)
    default_idx = option_letters.index(current_answer) if current_answer in option_letters else None

    selected_option = st.radio(
        label="Options",
        options=options,
        index=default_idx,
        key=f"radio_{idx}",
        label_visibility="collapsed",
    )

    # Save the answer
    if selected_option:
        st.session_state.answers[idx] = selected_option.split(".")[0].strip()

    st.markdown("<br/>", unsafe_allow_html=True)

    # ── Navigation Row ──────────────────────────────────────────────────────
    nav_col1, nav_col2, nav_col3 = st.columns([1.2, 1, 1.2])

    with nav_col1:
        if st.button("← Previous", key="btn_prev", use_container_width=True, disabled=idx == 0):
            st.session_state.current_idx -= 1
            st.rerun()

    with nav_col2:
        # Mini dots (up to 10)
        dots_html = ""
        display_total = min(total, 10)
        for i in range(display_total):
            color = "#6c63ff" if i == idx else ("#22c55e" if i in st.session_state.answers else "#374151")
            dots_html += f"<span style='display:inline-block; width:8px; height:8px; border-radius:50%; background:{color}; margin:2px;'></span>"
        st.markdown(f"<div style='text-align:center; padding-top:10px;'>{dots_html}</div>", unsafe_allow_html=True)

    with nav_col3:
        if idx < total - 1:
            can_proceed = not st.session_state.require_answer or idx in st.session_state.answers
            if st.button("Next →", key="btn_next", disabled=not can_proceed, use_container_width=True):
                st.session_state.current_idx += 1
                st.rerun()
        else:
            if st.button("Submit ✅", key="btn_submit", type="primary", use_container_width=True):
                st.session_state.phase = "results"
                st.session_state.submitted = True
                st.rerun()

    # ── Timer auto-refresh ──────────────────────────────────────────────────
    time.sleep(1)
    st.rerun()


# ---------------------------------------------------------------------------
# Results page
# ---------------------------------------------------------------------------


def render_results_page() -> None:
    mcqs: List[Dict[str, Any]] = st.session_state.mcqs
    answers: Dict[int, str] = st.session_state.answers
    total: int = len(mcqs)

    correct_count = sum(
        1
        for i, mcq in enumerate(mcqs)
        if answers.get(i) == mcq["correct_answer"]
    )
    wrong_count = sum(
        1
        for i in range(total)
        if i in answers and answers[i] != mcqs[i]["correct_answer"]
    )
    skipped_count = total - len(answers)
    score_pct = int((correct_count / total) * 100)

    # ── Score summary ───────────────────────────────────────────────────────
    st.markdown("<br/>", unsafe_allow_html=True)

    header_col, _ = st.columns([3, 1])
    with header_col:
        st.markdown(
            """
            <h1 style='font-size:2rem; font-weight:800; margin-bottom:0.25rem;'>
                📊 Exam Results
            </h1>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br/>", unsafe_allow_html=True)

    score_col, stats_col = st.columns([1, 2])

    with score_col:
        st.markdown(
            f"""
            <div class='score-circle'>
                <div class='score-pct'>{score_pct}%</div>
                <div class='score-label'>Score</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with stats_col:
        st.markdown(
            f"""
            <div class='stats-container'>
                <div class='stat-box' style='border-top: 3px solid #22c55e;'>
                    <div class='stat-val' style='color:#22c55e;'>{correct_count}</div>
                    <div class='stat-lbl'>Correct ✅</div>
                </div>
                <div class='stat-box' style='border-top: 3px solid #ef4444;'>
                    <div class='stat-val' style='color:#ef4444;'>{wrong_count}</div>
                    <div class='stat-lbl'>Wrong ❌</div>
                </div>
                <div class='stat-box' style='border-top: 3px solid #f59e0b;'>
                    <div class='stat-val' style='color:#f59e0b;'>{skipped_count}</div>
                    <div class='stat-lbl'>Skipped ⏭️</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Performance message
        st.markdown("<br/>", unsafe_allow_html=True)
        if score_pct >= 90:
            msg, emoji = "Outstanding performance! 🏆", "success"
        elif score_pct >= 70:
            msg, emoji = "Great job! Keep it up. 🎯", "info"
        elif score_pct >= 50:
            msg, emoji = "Good effort! Review the explanations below. 📚", "warning"
        else:
            msg, emoji = "Keep practising! Review the material and try again. 💪", "error"

        getattr(st, emoji)(msg)

    st.markdown("<hr/>", unsafe_allow_html=True)

    # ── Detailed review ─────────────────────────────────────────────────────
    st.markdown(
        "<h2 style='font-size:1.4rem; font-weight:700;'>📚 Detailed Review</h2>",
        unsafe_allow_html=True,
    )

    for i, mcq in enumerate(mcqs):
        user_ans = answers.get(i)
        correct_ans = mcq["correct_answer"]
        is_correct = user_ans == correct_ans
        is_skipped = user_ans is None

        card_cls = "mcq-card result-correct" if is_correct else "mcq-card result-wrong"
        status_icon = "✅" if is_correct else ("⏭️" if is_skipped else "❌")

        # Build options HTML with highlighting
        options_html = ""
        for opt in mcq["options"]:
            letter = opt.split(".")[0].strip()
            is_correct_opt = letter == correct_ans
            is_user_opt = letter == user_ans

            if is_correct_opt and is_user_opt:
                bg = "rgba(34,197,94,0.15)"
                border = "#22c55e"
                suffix = " ✅ Your answer (Correct)"
            elif is_correct_opt:
                bg = "rgba(34,197,94,0.10)"
                border = "#22c55e"
                suffix = " ✅ Correct answer"
            elif is_user_opt:
                bg = "rgba(239,68,68,0.12)"
                border = "#ef4444"
                suffix = " ❌ Your answer"
            else:
                bg = "transparent"
                border = "var(--border)"
                suffix = ""

            options_html += (
                f"<div style='background:{bg}; border:1px solid {border}; "
                f"border-radius:8px; padding:0.5rem 0.9rem; margin:4px 0; "
                f"font-size:0.9rem;'>{opt}{suffix}</div>"
            )

        st.markdown(
            f"""
            <div class='{card_cls}'>
                <div style='display:flex; justify-content:space-between; align-items:flex-start;'>
                    <div style='font-weight:600; font-size:0.82rem; color:var(--text-secondary);'>
                        Question {i + 1}
                    </div>
                    <span style='font-size:1.2rem;'>{status_icon}</span>
                </div>
                <p style='font-size:1rem; font-weight:600; margin: 0.5rem 0 1rem;'>
                    {mcq["question"]}
                </p>
                {options_html}
                <div style='margin-top:1rem; padding:0.75rem 1rem;
                    background:rgba(108,99,255,0.08); border-radius:8px;
                    border-left:3px solid var(--accent);'>
                    <span style='font-weight:600; color:var(--accent-light); font-size:0.85rem;'>
                        💡 Explanation
                    </span>
                    <p style='margin:0.3rem 0 0; font-size:0.88rem; color:var(--text-secondary);'>
                        {mcq["explanation"]}
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br/>", unsafe_allow_html=True)
    if st.button("🔄 Start a New Exam", use_container_width=False):
        _reset_exam()
        st.rerun()


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------


def main() -> None:
    # ── Debug Mode (Preview UI) ───────────────────────────────────────────
    query_params = st.query_params
    if "debug" in query_params:
        debug_mode = query_params["debug"]
        if debug_mode == "exam" and st.session_state.phase == "setup":
            st.session_state.phase = "exam"
            st.session_state.pdf_name = "Debug_Exam.pdf"
            st.session_state.difficulty = "Medium"
            st.session_state.mcqs = [{
                "question": "Which component of the plant cell is primarily responsible for photosynthesis?",
                "options": ["A. Mitochondria", "B. Chloroplast", "C. Nucleus", "D. Ribosome"],
                "correct_answer": "B",
                "explanation": "Chloroplasts are the organelles in plant cells that carry out photosynthesis."
            }] * 5
            st.session_state.exam_start_time = time.time()
            st.session_state.total_seconds = 30 * 5
        elif debug_mode == "results" and st.session_state.phase == "setup":
            st.session_state.phase = "results"
            st.session_state.pdf_name = "Debug_Results.pdf"
            st.session_state.mcqs = [{
                "question": "Which component of the plant cell is primarily responsible for photosynthesis?",
                "options": ["A. Mitochondria", "B. Chloroplast", "C. Nucleus", "D. Ribosome"],
                "correct_answer": "B",
                "explanation": "Chloroplasts are the organelles in plant cells that carry out photosynthesis."
            }]
            st.session_state.answers = {0: "A"}  # Wrong answer
            st.session_state.submitted = True

    render_sidebar()

    phase = st.session_state.phase

    if phase == "setup":
        render_setup_page()
    elif phase == "exam":
        render_exam_page()
    elif phase == "results":
        render_results_page()


if __name__ == "__main__":
    main()
