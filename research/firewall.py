"""Best-effort runtime guard for Train-only parquet reads.

This guards pandas and the public PyArrow parquet readers used by the research
code. It is an audit guard, not an operating-system sandbox: code that loads
native readers directly can still bypass Python-level wrappers.
"""
import functools
import json
import os
import sys
from pathlib import Path

ACCESSES = set()
GUARDED_READS = set()
_ALLOWED_ARTIFACTS = set()
_PATCHED = False
_PANDAS_READ_DEPTH = 0


def _canonical_source(source):
    """Return an allowed canonical parquet path or reject ambiguous sources."""
    if not isinstance(source, (str, bytes, os.PathLike)):
        raise PermissionError("Train-only parquet guard requires a filesystem path")
    supplied = Path(os.fsdecode(source))
    supplied_name = str(supplied).lower()
    if "_valid" in supplied_name or "raw_target" in supplied_name:
        raise PermissionError(f"Train-only parquet guard denied {supplied.name}")
    try:
        canonical = supplied.resolve(strict=True)
    except OSError as error:
        raise PermissionError(f"Train-only parquet source is unavailable: {supplied}") from error
    rendered = str(canonical).lower()
    name = canonical.name.lower()
    if "_valid" in rendered or "raw_target" in rendered:
        raise PermissionError(f"Train-only parquet guard denied {canonical.name}")
    if rendered not in _ALLOWED_ARTIFACTS and not name.endswith("_train.parquet"):
        raise PermissionError(f"Train-only parquet guard denied {canonical.name}")
    return canonical


def _guard_reader(name, reader, source_position=0, source_keyword="path"):
    @functools.wraps(reader)
    def guarded(*args, **kwargs):
        global _PANDAS_READ_DEPTH
        source = args[source_position] if len(args) > source_position else kwargs.get(source_keyword)
        if name == "pandas.read_parquet":
            canonical = _canonical_source(source)
            if str(canonical).lower() not in _ALLOWED_ARTIFACTS:
                ACCESSES.add(str(canonical))
            GUARDED_READS.add(name)
            _PANDAS_READ_DEPTH += 1
            try:
                return reader(*args, **kwargs)
            finally:
                _PANDAS_READ_DEPTH -= 1
        if not isinstance(source, (str, bytes, os.PathLike)) and name.startswith("pyarrow.parquet."):
            if _PANDAS_READ_DEPTH == 0:
                raise PermissionError("Train-only parquet guard rejects unverified file-like sources")
            GUARDED_READS.add(name)
            return reader(*args, **kwargs)
        canonical = _canonical_source(source)
        if str(canonical).lower() not in _ALLOWED_ARTIFACTS:
            ACCESSES.add(str(canonical))
        GUARDED_READS.add(name)
        return reader(*args, **kwargs)
    return guarded


def install(allowed_artifacts=()):
    """Deny Valid/raw-target parquet reads through standard Python reader APIs."""
    global _PATCHED
    _ALLOWED_ARTIFACTS.update(str(Path(path).resolve()).lower() for path in allowed_artifacts)
    if _PATCHED:
        return

    import pandas as pd

    pd.read_parquet = _guard_reader("pandas.read_parquet", pd.read_parquet)

    # Pandas is the usual entry point, but direct PyArrow calls must obey the
    # same rule. Wrap file-path readers and reject file-like/native sources,
    # whose provenance cannot be checked here.
    try:
        import pyarrow.parquet as pq
        import pyarrow.dataset as ds
    except ImportError:
        pq = None
        ds = None
    if pq is not None:
        for reader_name in ("read_table", "read_pandas"):
            reader = getattr(pq, reader_name, None)
            if reader is not None:
                setattr(pq, reader_name, _guard_reader(f"pyarrow.parquet.{reader_name}", reader,
                                                       source_keyword="source"))
        for reader_name in ("read_metadata", "read_schema", "read_statistics"):
            reader = getattr(pq, reader_name, None)
            if reader is not None:
                setattr(pq, reader_name, _guard_reader(f"pyarrow.parquet.{reader_name}", reader,
                                                       source_keyword="where"))

        original_parquet_file = pq.ParquetFile

        class GuardedParquetFile(original_parquet_file):
            def __init__(self, source, *args, **kwargs):
                canonical = _canonical_source(source)
                if str(canonical).lower() not in _ALLOWED_ARTIFACTS:
                    ACCESSES.add(str(canonical))
                GUARDED_READS.add("pyarrow.parquet.ParquetFile")
                super().__init__(source, *args, **kwargs)

        pq.ParquetFile = GuardedParquetFile

        if ds is not None:
            original_dataset = ds.dataset

            @functools.wraps(original_dataset)
            def guarded_dataset(source, *args, **kwargs):
                canonical = _canonical_source(source)
                if not canonical.is_file():
                    raise PermissionError("Train-only parquet guard rejects directory datasets")
                if str(canonical).lower() not in _ALLOWED_ARTIFACTS:
                    ACCESSES.add(str(canonical))
                GUARDED_READS.add("pyarrow.dataset.dataset")
                return original_dataset(source, *args, **kwargs)

            ds.dataset = guarded_dataset

    def audit(event, args):
        if event != "open" or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else 0
        if (isinstance(mode, str) and any(flag in mode for flag in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        ):
            return
        path = os.fsdecode(args[0])
        if path.lower().endswith(".parquet"):
            canonical = _canonical_source(path)
            if str(canonical).lower() not in _ALLOWED_ARTIFACTS:
                ACCESSES.add(str(canonical))

    sys.addaudithook(audit)
    _PATCHED = True


def save(path):
    Path(path).write_text(json.dumps({
        "opened_parquets": sorted(ACCESSES),
        "guarded_reader_apis": sorted(GUARDED_READS),
        "valid_evaluation": False,
        "raw_target_reads": False,
    }, indent=2) + "\n")
