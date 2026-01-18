import json
from pathlib import Path

APP_NAME = "DictionaryApp"


def _app_support_dir() -> Path:
    base = Path.home() / "Library" / "Application Support"
    return base / APP_NAME


def vocab_path() -> Path:
    d = _app_support_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "vocab.json"


def load_vocab(path: Path | None = None) -> list[dict]:
    path = path or vocab_path()
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("vocab.json должен содержать список объектов.")

    for it in data:
        if "topic" not in it or not str(it["topic"]).strip():
            it["topic"] = "Simple words"

    return data


def save_vocab(items: list[dict], path: Path | None = None) -> None:
    path = path or vocab_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
