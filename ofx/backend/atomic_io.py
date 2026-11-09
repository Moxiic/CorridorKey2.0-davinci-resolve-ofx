"""Same-directory atomic publication with bounded Windows sharing retries."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time


def replace_file(source, destination, *, attempts=8):
    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except OSError as error:
            # Readers/virus scanners can briefly open files without delete sharing.
            # Real permissions/path/disk errors must still propagate.
            transient = isinstance(error, PermissionError) or getattr(error, "winerror", None) in (5, 32, 33)
            if not transient or attempt + 1 == attempts:
                raise
            time.sleep(min(.01 * 2**attempt, .16))


def atomic_text(path: Path, value: str):
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(value)
        replace_file(temporary, path)
    finally:
        try:
            Path(temporary).unlink(missing_ok=True)
        except OSError:
            pass


def atomic_json(path: Path, value):
    atomic_text(path, json.dumps(value))
