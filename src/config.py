"""Central configuration for models, retrieval, and paths."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "data" / "knowledge_base"
EVALS_DIR = ROOT / "evals"

# Models (override via env or the Streamlit sidebar)
MAIN_MODEL = os.getenv("MAIN_MODEL", "claude-sonnet-4-5")
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "claude-haiku-4-5")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "claude-sonnet-4-5")

# Retrieval
TOP_K = int(os.getenv("TOP_K", "4"))
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.05"))

# Generation
MAX_TOKENS = 1024
TEMPERATURE = 0.2
MAX_TOOL_TURNS = 5
