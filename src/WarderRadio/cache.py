"""Bound only generated RAM-cache files; never traverse user asset folders."""
import os
import re
import tempfile


def write_atomic(path, data):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(path), prefix='.warder-cache-', delete=False) as stream:
            temporary = stream.name
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try: os.unlink(temporary)
            except OSError: pass


def prune(directory, pattern, max_files, max_bytes, keep=()):
    """Keep recent generated entries within a count/byte budget, without links."""
    try:
        if os.path.islink(directory): return
        protected = {os.path.abspath(str(path)) for path in keep if path}
        entries = []
        with os.scandir(directory) as scan:
            for entry in scan:
                if re.fullmatch(pattern, entry.name) and entry.is_file(follow_symlinks=False):
                    details = entry.stat(follow_symlinks=False)
                    entries.append((entry.path, details.st_mtime, details.st_size))
        entries.sort(key=lambda row: row[1], reverse=True)
        count = size = 0
        for path, unused, length in entries:
            count += 1
            size += length
            if (count > max_files or size > max_bytes) and os.path.abspath(path) not in protected:
                try: os.unlink(path)
                except OSError: pass
    except OSError:
        pass  # Cache housekeeping must never break programme display.
