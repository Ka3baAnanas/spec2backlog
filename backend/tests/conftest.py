import os
import tempfile
import uuid
from pathlib import Path

_TMP = Path(tempfile.gettempdir()) / f"spec2backlog-tests-{uuid.uuid4().hex}"
_TMP.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["UPLOADS_DIR"] = str(_TMP / "uploads")
os.environ["DEMO_DELAY_MS"] = "0"
os.environ["USE_CELERY"] = "false"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["EMBEDDING_PROVIDER"] = "fake"
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["CHROMA_HOST"] = ""
os.environ["SIMILAR_MIN_SCORE"] = "0.0"
os.environ["LEXICAL_MIN_SCORE"] = "0.05"
