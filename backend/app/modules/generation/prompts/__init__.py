from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
DEFAULT_VERSION = "v1"


def load_template(name: str, version: str = DEFAULT_VERSION) -> str:
    path = PROMPTS_DIR / f"{version}_{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8").strip()
