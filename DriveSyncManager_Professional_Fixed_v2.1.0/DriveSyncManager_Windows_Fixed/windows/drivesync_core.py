"""Reliable, platform-neutral file transfer primitives for DriveSync Manager."""
from __future__ import annotations

import errno
import hashlib
import inspect
import os
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

CHUNK_SIZE = 1024 * 1024
GOOGLE_NATIVE_EXTENSIONS = {
    ".gdoc", ".gsheet", ".gslides", ".gdraw", ".gform", ".gmap", ".gsite"
}

# Windows error codes that can be transient when reading virtual/network filesystems.
TRANSIENT_WINERRORS = {121, 1450, 64, 995, 1231, 1232}
TRANSIENT_ERRNOS = {
    errno.EINTR,
    errno.EAGAIN,
    getattr(errno, "ETIMEDOUT", 110),
    getattr(errno, "ECONNRESET", 104),
    getattr(errno, "ECONNABORTED", 103),
    getattr(errno, "EIO", 5),
}


def call_with_supported_kwargs(function, **kwargs):
    """Call a dependency function with only keyword arguments its installed API supports.

    This keeps DriveSync compatible with multiple gdown releases, whose public
    function signatures have changed over time. If signature introspection is not
    available, make the call unchanged so the original exception remains visible.
    """
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return function(**kwargs)

    parameters = signature.parameters.values()
    accepts_extra = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters)
    if accepts_extra:
        supported = kwargs
    else:
        accepted_names = set(signature.parameters)
        supported = {key: value for key, value in kwargs.items() if key in accepted_names}
    return function(**supported)


def is_google_workspace_stub(path: os.PathLike | str) -> bool:
    return Path(path).suffix.lower() in GOOGLE_NATIVE_EXTENSIONS


def is_google_quota_error(message: object) -> bool:
    text = str(message).lower()
    # Do not treat generic "failed to retrieve file url" as a quota error: it can
    # also mean malformed URLs, permissions, or a changed Google Drive page.
    return any(term in text for term in (
        "too many users have viewed or downloaded",
        "download quota exceeded",
        "downloadquotaexceeded",
        "user rate limit exceeded",
        "userratelimitexceeded",
        "quota exceeded",
        "rate limit exceeded",
        "too many requests",
    ))


def is_transient_io_error(exc: BaseException) -> bool:
    winerror = getattr(exc, "winerror", None)
    if winerror in TRANSIENT_WINERRORS:
        return True
    if isinstance(exc, (TimeoutError, ConnectionResetError, ConnectionAbortedError, InterruptedError)):
        return True
    return isinstance(exc, OSError) and exc.errno in TRANSIENT_ERRNOS


def paths_overlap(source: str, destination: str) -> bool:
    """Return True when either normalized path is equal to or nested under the other."""
    src = os.path.normcase(os.path.realpath(os.path.abspath(os.path.expanduser(source))))
    dst = os.path.normcase(os.path.realpath(os.path.abspath(os.path.expanduser(destination))))
    try:
        common = os.path.commonpath([src, dst])
    except ValueError:  # Different Windows drives.
        return False
    return common == src or common == dst


def copy_file_atomic(
    source: os.PathLike | str,
    destination: os.PathLike | str,
    *,
    chunk_size: int = CHUNK_SIZE,
    max_retries: int = 5,
    base_backoff: float = 0.5,
    on_progress: Optional[Callable[[int, int, float, str], None]] = None,
    on_retry: Optional[Callable[[int, BaseException], None]] = None,
    source_opener=None,
) -> dict:
    """Copy a file in bounded chunks and atomically replace destination on success.

    A failed transfer leaves an existing destination untouched and removes this
    attempt's temporary file. Source reads are retried from the last committed
    offset for known transient I/O errors. Returns byte count and SHA-256 digest.
    """
    src = os.fspath(source)
    dst = os.fspath(destination)
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    if max_retries < 0:
        raise ValueError("max_retries cannot be negative")
    if os.path.isdir(src):
        raise IsADirectoryError(src)

    source_stat = os.stat(src)
    expected_size = source_stat.st_size
    parent = os.path.dirname(os.path.abspath(dst)) or "."
    os.makedirs(parent, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".drivesync_part_", suffix=".tmp", dir=parent)
    os.close(fd)
    opener = source_opener or open
    started = time.monotonic()
    transferred = 0
    digest = hashlib.sha256()
    try:
        with opener(src, "rb") as reader, open(temporary, "wb") as writer:
            while transferred < expected_size:
                wanted = min(chunk_size, expected_size - transferred)
                attempt = 0
                while True:
                    try:
                        # A previous transient read can leave stream position uncertain.
                        reader.seek(transferred)
                        block = reader.read(wanted)
                        break
                    except OSError as exc:
                        if not is_transient_io_error(exc) or attempt >= max_retries:
                            raise
                        attempt += 1
                        if on_retry:
                            on_retry(attempt, exc)
                        time.sleep(min(base_backoff * (2 ** (attempt - 1)), 8.0))
                if not block:
                    raise IOError(
                        f"Unexpected end of source after {transferred} of {expected_size} bytes; "
                        "the source may be offline, incomplete, or changing."
                    )
                writer.write(block)
                digest.update(block)
                transferred += len(block)
                elapsed = max(time.monotonic() - started, 0.001)
                speed = transferred / elapsed
                if on_progress:
                    on_progress(transferred, expected_size, speed, "copy")
            writer.flush()
            os.fsync(writer.fileno())

        if transferred != expected_size or os.path.getsize(temporary) != expected_size:
            raise IOError(
                f"Size verification failed: expected {expected_size} bytes, copied {transferred}."
            )

        # Confirm the source did not change while it was being read.
        final_stat = os.stat(src)
        if final_stat.st_size != source_stat.st_size or final_stat.st_mtime_ns != source_stat.st_mtime_ns:
            raise IOError("Source changed during transfer; destination was not replaced. Please retry.")

        os.replace(temporary, dst)
        try:
            os.utime(dst, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        except OSError:
            # Metadata is best-effort. Data verification and commit already succeeded.
            pass
        elapsed = max(time.monotonic() - started, 0.001)
        return {"bytes": transferred, "sha256": digest.hexdigest(), "seconds": elapsed,
                "bytes_per_second": transferred / elapsed}
    except BaseException:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise
