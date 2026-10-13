"""Synthetic filesystem paths only; never changes production safety checks."""
from pathlib import Path
import re
import tempfile


def fixture_temp(prefix='tmp'):
    # These shell/proc fixtures need whitespace-free paths. Prefer the harness
    # area, with Linux /tmp fallback for ordinary CI; do not inherit a spaced
    # workstation TMPDIR and do not disable native path/ownership checks.
    base=Path('/tmp/opencode')
    return tempfile.TemporaryDirectory(dir=base if base.is_dir() else '/tmp',prefix=prefix)


def fixed_paths(text,base,prefixes):
    # One pass: sequential replacements would rewrite an inserted /tmp path
    # again when processing the original script's /tmp prefix.
    pattern='|'.join(re.escape(prefix) for prefix in sorted(prefixes,key=len,reverse=True))
    return re.sub(pattern,lambda match:str(base/match[0].strip('/'))+('/' if match[0].endswith('/') else ''),text)
