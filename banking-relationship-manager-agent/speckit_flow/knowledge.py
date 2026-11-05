from __future__ import annotations

from pathlib import Path

from speckit_flow.models import STAGES, KnowledgeDoc

DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / ".specify" / "knowledge"


def _parse(path: Path) -> KnowledgeDoc:
    title = path.stem
    stages: tuple[str, ...] = ("all",)
    try:
        head = path.read_text(encoding="utf-8").splitlines()[:15]
    except OSError:
        head = []
    for line in head:
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key == "title" and value.strip():
            title = value.strip()
        elif key == "stages" and value.strip():
            parsed = tuple(s.strip().lower() for s in value.split(",") if s.strip())
            stages = tuple(s for s in parsed if s == "all" or s in STAGES) or ("all",)
    return KnowledgeDoc(path.name, title, stages)


def list_knowledge(
    stage: str | None = None, folder: Path = DEFAULT_KNOWLEDGE_DIR
) -> list[KnowledgeDoc]:
    """Return titles and paths only; document bodies are never loaded into context."""
    if not folder.is_dir():
        return []
    docs = [_parse(p) for p in sorted(folder.glob("*.md")) if p.name.lower() != "readme.md"]
    if stage:
        docs = [d for d in docs if "all" in d.stages or stage in d.stages]
    return docs
