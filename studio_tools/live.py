"""Observe saved app files without including databases, secrets or private records."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {".py", ".html", ".css", ".js", ".json", ".svg", ".png", ".jpg", ".webp"}


def revision(root=ROOT):
    """Return a content revision so a development browser can refresh after a save."""
    digest = hashlib.sha256()
    for path in sorted((Path(root) / "app").rglob("*")):
        if (
            path.is_file()
            and not path.is_symlink()
            and path.suffix in SUFFIXES
            and "__pycache__" not in path.parts
        ):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()
