"""
DriveSync Manager — Linux Edition
Sync local folders, Google Drive mounts (FUSE/rclone), and public Drive links.
"""
import os
import sys
import time
import queue
import shutil
import hashlib
import threading
import subprocess
import traceback
import tempfile
import contextlib
import io
import json
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from drivesync_core import (
    GOOGLE_NATIVE_EXTENSIONS, copy_file_atomic, call_with_supported_kwargs,
    is_google_quota_error as _core_is_google_quota_error,
    is_google_workspace_stub, paths_overlap as _core_paths_overlap,
)

APP_NAME = "DriveSync Manager"
APP_VERSION = "2.1.1"
PLATFORM = "Linux"

# Google Workspace files in a Drive mount are link/metadata stubs,
# not ordinary files that shutil.copy2 can copy. Export/download these from Drive.
GOOGLE_NATIVE_EXTENSIONS = {
    ".gdoc", ".gsheet", ".gslides", ".gdraw", ".gform", ".gmap", ".gsite"
}

# Max retries per file before giving up
MAX_RETRIES = 3
# Chunk size for file hashing (4 MB)
HASH_CHUNK_SIZE = 4 * 1024 * 1024


def is_google_quota_error(message):
    """Use precise Google quota/rate-limit classification shared with the transfer core."""
    return _core_is_google_quota_error(message)


def is_url(value):
    """Check if the value looks like a URL."""
    return value.strip().lower().startswith(("https://", "http://"))


def safe_name(name):
    """Sanitize a file name for the filesystem."""
    # Linux allows most chars except / and null, but sanitize for safety
    return name.replace("/", "_").replace("\0", "_")


def file_hash(path, algorithm="md5"):
    """Compute a fast file hash for change detection."""
    h = hashlib.new(algorithm)
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(HASH_CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def paths_overlap(path_a, path_b):
    """Check equality or nesting using normalized real paths and component boundaries."""
    return _core_paths_overlap(path_a, path_b)


class RetryQueue:
    """Thread-safe retry queue for failed file operations."""

    def __init__(self):
        self._lock = threading.Lock()
        self._items = {}  # path -> {"src", "dst", "retries", "last_error", "is_quota"}

    def add(self, src, dst, error_msg, is_quota=False):
        with self._lock:
            key = src
            if key in self._items:
                self._items[key]["retries"] += 1
                self._items[key]["last_error"] = error_msg
                self._items[key]["is_quota"] = bool(is_quota)
            else:
                self._items[key] = {
                    "src": src,
                    "dst": dst,
                    "retries": 1,
                    "last_error": error_msg,
                    "is_quota": is_quota,
                }

    def get_retryable(self, include_quota=False, force=False):
        """Return retry candidates. Manual retries can override quota/max-attempt filters."""
        with self._lock:
            return [
                item for item in self._items.values()
                if (force or item.get("retries", 0) <= MAX_RETRIES)
                and (include_quota or not item.get("is_quota", False))
            ]

    def get_all(self):
        with self._lock:
            return list(self._items.values())

    def remove(self, src):
        with self._lock:
            self._items.pop(src, None)

    def clear(self):
        with self._lock:
            self._items.clear()

    def __len__(self):
        with self._lock:
            return len(self._items)

    def save(self, path):
        """Persist retry queue atomically so interruption cannot corrupt the queue file."""
        with self._lock:
            temp_path = None
            try:
                parent = os.path.dirname(os.path.abspath(path)) or "."
                os.makedirs(parent, exist_ok=True)
                fd, temp_path = tempfile.mkstemp(prefix=".drivesync_queue_", suffix=".tmp", dir=parent)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(list(self._items.values()), f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_path, path)
            except OSError:
                if temp_path:
                    try: os.remove(temp_path)
                    except OSError: pass

    def load(self, path):
        """Load retry queue from disk."""
        with self._lock:
            try:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        items = json.load(f)
                    if not isinstance(items, list):
                        return
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        if not isinstance(item.get("src"), str) or not isinstance(item.get("dst"), str):
                            continue
                        item.setdefault("retries", 1)
                        item.setdefault("last_error", "Previous transfer failed")
                        item.setdefault("is_quota", False)
                        self._items[item["src"]] = item
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass


class SyncStats:
    """Thread-safe sync statistics."""

    def __init__(self):
        self._lock = threading.Lock()
        self.copied = 0
        self.updated = 0
        self.skipped = 0
        self.errors = 0

    def inc_copied(self):
        with self._lock:
            self.copied += 1

    def inc_updated(self):
        with self._lock:
            self.updated += 1

    def inc_skipped(self):
        with self._lock:
            self.skipped += 1

    def inc_errors(self):
        with self._lock:
            self.errors += 1

    def reset(self):
        with self._lock:
            self.copied = self.updated = self.skipped = self.errors = 0

    def summary(self):
        with self._lock:
            return f"Copied: {self.copied}  Updated: {self.updated}  Skipped: {self.skipped}  Errors: {self.errors}"

    def values(self):
        with self._lock:
            return self.copied, self.updated, self.skipped, self.errors


class DriveSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} — {PLATFORM}")
        self.root.geometry("920x700")
        self.root.minsize(780, 600)
        self.events = queue.Queue()
        self.worker = None
        self.stop_event = threading.Event()
        self.source_var = tk.StringVar()
        self.dest_var = tk.StringVar()
        self.interval_var = tk.StringVar(value="30")
        self.schedule_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0)
        self.stats = SyncStats()
        self.retry_queue = RetryQueue()
        self._loaded_retry_queue_path = None
        self._build_ui()
        self.root.after(150, self._poll_events)

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        # Header
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text="DriveSync Manager", font=("Ubuntu", 20, "bold")).pack(side="left")
        ttk.Label(header, text=f"v{APP_VERSION} • Linux", font=("Ubuntu", 9), foreground="#888").pack(
            side="left", padx=(12, 0), anchor="s", pady=(0, 4))

        ttk.Label(outer,
                  text="Copy and update files from a local folder, Google Drive mount (FUSE/rclone/google-drive-ocamlfuse), or a public Drive link.",
                  wraplength=850).pack(anchor="w", pady=(0, 10))

        # Source
        source_frame = ttk.LabelFrame(outer, text="1. Source", padding=10)
        source_frame.pack(fill="x", pady=4)
        src_row = ttk.Frame(source_frame)
        src_row.pack(fill="x")
        ttk.Entry(src_row, textvariable=self.source_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(src_row, text="Browse…", command=self._browse_source).pack(side="left")
        ttk.Label(source_frame,
                  text="Accepts: local folder path, Google Drive mount path (~/google-drive/...), or a public/shared Drive URL.",
                  foreground="#555", wraplength=820).pack(anchor="w", pady=(6, 0))

        # Destination
        dest_frame = ttk.LabelFrame(outer, text="2. Destination folder", padding=10)
        dest_frame.pack(fill="x", pady=4)
        dst_row = ttk.Frame(dest_frame)
        dst_row.pack(fill="x")
        ttk.Entry(dst_row, textvariable=self.dest_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(dst_row, text="Browse…", command=self._browse_dest).pack(side="left")
        ttk.Label(dest_frame, text="Files deleted from source are NOT removed from destination.",
                  foreground="#555").pack(anchor="w", pady=(6, 0))

        # Automation options
        options = ttk.LabelFrame(outer, text="3. Options", padding=10)
        options.pack(fill="x", pady=4)
        opt_row = ttk.Frame(options)
        opt_row.pack(fill="x")
        ttk.Checkbutton(opt_row, text="Repeat sync automatically", variable=self.schedule_var).pack(side="left")
        ttk.Label(opt_row, text="Every").pack(side="left", padx=(18, 5))
        ttk.Spinbox(opt_row, from_=1, to=1440, width=7, textvariable=self.interval_var).pack(side="left")
        ttk.Label(opt_row, text="minutes").pack(side="left", padx=(5, 0))
        ttk.Label(options,
                  text="Web links: only public/shared links work. Private links need a local Drive mount.",
                  foreground="#555", wraplength=800).pack(anchor="w", pady=(6, 0))

        # Action buttons
        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(8, 4))
        self.sync_btn = ttk.Button(buttons, text="▶ Sync now", command=self.start_sync)
        self.sync_btn.pack(side="left")
        self.stop_btn = ttk.Button(buttons, text="⏹ Stop", command=self.stop_sync, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        self.retry_btn = ttk.Button(buttons, text="🔄 Retry failed", command=self.retry_failed, state="disabled")
        self.retry_btn.pack(side="left")
        ttk.Button(buttons, text="📂 Open destination", command=self.open_destination).pack(side="left", padx=(16, 0))
        ttk.Button(buttons, text="📋 Open log", command=self.open_log).pack(side="left", padx=8)

        # Status bar
        status = ttk.Frame(outer)
        status.pack(fill="x", pady=(8, 2))
        ttk.Label(status, textvariable=self.status_var, font=("Ubuntu", 9)).pack(side="left")
        self.count_label = ttk.Label(status, text="Copied: 0  Updated: 0  Skipped: 0  Errors: 0",
                                     font=("Ubuntu", 9))
        self.count_label.pack(side="right")

        self.progress = ttk.Progressbar(outer, variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x", pady=(0, 6))

        # Log area
        log_frame = ttk.LabelFrame(outer, text="Activity / error log", padding=8)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_frame, height=14, wrap="word", state="disabled",
                                font=("Monospace", 9), bg="#1e1e1e", fg="#d4d4d4",
                                insertbackground="#d4d4d4", selectbackground="#264f78")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Configure log text tags for colored output
        self.log_text.tag_configure("error", foreground="#f44747")
        self.log_text.tag_configure("success", foreground="#6a9955")
        self.log_text.tag_configure("warning", foreground="#cca700")
        self.log_text.tag_configure("info", foreground="#569cd6")
        self.log_text.tag_configure("default", foreground="#d4d4d4")

        self._log("Ready. Choose a source and destination, then click Sync now.", "info")

    # ── Browse dialogs ──

    def _browse_source(self):
        folder = filedialog.askdirectory(title="Select source folder")
        if folder:
            self.source_var.set(folder)

    def _browse_dest(self):
        folder = filedialog.askdirectory(title="Select destination folder")
        if folder:
            self.dest_var.set(folder)

    # ── Logging ──

    def log_path(self):
        dest = self.dest_var.get().strip()
        if dest:
            expanded = os.path.expandvars(os.path.expanduser(dest))
            if not os.path.isabs(expanded):
                expanded = os.path.join(self.app_cwd, expanded)
            return os.path.join(os.path.abspath(expanded), "DriveSyncManager.log")
        return os.path.join(os.path.expanduser("~"), "DriveSyncManager.log")

    def _log(self, msg, tag="default"):
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] {msg}"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        try:
            p = self.log_path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            if os.path.exists(p) and os.path.getsize(p) > 2 * 1024 * 1024:
                rotated = p + ".1"
                try:
                    if os.path.exists(rotated):
                        os.remove(rotated)
                    os.replace(p, rotated)
                except OSError:
                    pass
            with open(p, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    # ── Retry queue path ──

    def _retry_queue_path(self):
        dest = self.dest_var.get().strip()
        if dest:
            expanded = os.path.expandvars(os.path.expanduser(dest))
            if not os.path.isabs(expanded):
                expanded = os.path.join(self.app_cwd, expanded)
            return os.path.join(os.path.abspath(expanded), ".drivesync_retry_queue.json")
        return os.path.join(os.path.expanduser("~"), ".drivesync_retry_queue.json")

    # ── Symlink safety ──

    def _is_safe_symlink(self, path, source_root):
        """
        Check if a symlink target is safe to follow (not circular, not outside source).
        On Linux, we skip symlinks by default to prevent recursive loops.
        """
        try:
            target = os.path.realpath(path)
            source_real = os.path.realpath(source_root)
            # Don't follow symlinks that point outside the source tree
            if not target.startswith(source_real + os.sep) and target != source_real:
                return False
            # Don't follow symlinks that point to a parent directory (circular)
            if source_real.startswith(target + os.sep) or source_real == target:
                return False
            return True
        except OSError:
            return False

    # ── Sync start/stop ──

    def start_sync(self):
        source = self.source_var.get().strip()
        dest = self.dest_var.get().strip()

        if not source or not dest:
            messagebox.showwarning(APP_NAME, "Enter a source and destination folder.")
            return

        if not is_url(source):
            expanded_source = os.path.expandvars(os.path.expanduser(source))
            if not os.path.isdir(expanded_source):
                messagebox.showerror(APP_NAME,
                    "Source folder was not found.\n\n"
                    "If using a Google Drive mount, confirm the mount is active and the path exists.\n"
                    "Common mounts: ~/google-drive, ~/gdrive, or a custom FUSE/rclone path.")
                return

        dest_abs = os.path.abspath(os.path.expandvars(os.path.expanduser(dest)))

        if not is_url(source):
            source_abs = os.path.abspath(os.path.expandvars(os.path.expanduser(source)))
            if paths_overlap(source_abs, dest_abs):
                messagebox.showerror(APP_NAME,
                    "Source and destination must not be the same folder or nested inside each other.")
                return

        try:
            interval = max(1, int(self.interval_var.get()))
        except ValueError:
            messagebox.showerror(APP_NAME, "Repeat interval must be a whole number of minutes.")
            return

        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME, "A sync is already running.")
            return

        self.stop_event.clear()
        self.stats.reset()
        queue_path = os.path.join(dest_abs, ".drivesync_retry_queue.json")
        if queue_path != self._loaded_retry_queue_path:
            self.retry_queue.clear()
            self.retry_queue.load(queue_path)
            self._loaded_retry_queue_path = queue_path
        self.progress_var.set(0)
        self.sync_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.retry_btn.configure(state="disabled")
        self.status_var.set("Starting…")

        self.worker = threading.Thread(
            target=self._sync_loop,
            args=(source, dest_abs, self.schedule_var.get(), interval),
            daemon=True
        )
        self.worker.start()

    def stop_sync(self):
        self.stop_event.set()
        self.status_var.set("Stopping after current item…")
        self._log("Stop requested.", "warning")

    def retry_failed(self):
        """Retry items in the retry queue."""
        retryable = self.retry_queue.get_retryable(include_quota=True, force=True)
        if not retryable:
            messagebox.showinfo(APP_NAME, "No failed items in the queue.")
            return

        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME, "A sync is already running. Wait for it to finish.")
            return

        self.stop_event.clear()
        self.sync_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.retry_btn.configure(state="disabled")

        self.worker = threading.Thread(target=self._retry_loop, args=(retryable,), daemon=True)
        self.worker.start()

    def _retry_loop(self, items):
        """Process retry queue items."""
        self._send("log", f"Manually retrying {len(items)} failed item(s)… quota-blocked files may still be rejected by Google.", "info")
        total = max(1, len(items))
        for idx, item in enumerate(items, 1):
            if self.stop_event.is_set():
                break
            self._send("status", f"Retrying ({idx}/{total}): {os.path.basename(item['src'])}")
            self._copy_if_needed(item["src"], item["dst"])
            self._send("progress", int(idx * 100 / total))

        remaining = self.retry_queue.get_all()
        self.retry_queue.save(self._retry_queue_path())
        if remaining:
            self._send("log", f"Retry complete. {len(remaining)} item(s) still failed.", "warning")
        else:
            self._send("log", "All retried items succeeded.", "success")
        self._send("done", None)

    # ── Event system ──

    def _send(self, kind, value=None, tag="default"):
        self.events.put((kind, value, tag))

    def _sync_loop(self, source, dest, repeat, interval):
        while True:
            try:
                self._send("log", f"Sync started. Source: {source}", "info")
                self._send("log", f"Destination: {dest}", "info")
                os.makedirs(dest, exist_ok=True)

                if is_url(source):
                    self._sync_public_drive_url(source, dest)
                else:
                    self._sync_local(source, dest)

                # Process retry queue
                retryable = self.retry_queue.get_retryable()
                if retryable:
                    self._send("log", f"Retrying {len(retryable)} failed item(s)…", "warning")
                    for item in retryable:
                        if self.stop_event.is_set():
                            break
                        self._copy_if_needed(item["src"], item["dst"])

                c, u, s, e = self.stats.values()
                self._send("log", f"Sync finished. Copied: {c}, Updated: {u}, Skipped: {s}, Errors: {e}.", "success")

                # Save remaining retry items
                remaining = self.retry_queue.get_all()
                self.retry_queue.save(self._retry_queue_path())
                if remaining:
                    self._send("log", f"{len(remaining)} item(s) remain in retry queue (saved to disk).", "warning")

            except Exception as e:
                self.stats.inc_errors()
                self._send("log", f"CRITICAL ERROR: {e}", "error")
                self._send("log", traceback.format_exc(), "error")

            if not repeat or self.stop_event.is_set():
                break

            self._send("status", f"Waiting {interval} minute(s) until next sync…")
            for _ in range(interval * 60):
                if self.stop_event.wait(1):
                    break
            if self.stop_event.is_set():
                break

        self._send("done", None)

    # ── Google Drive web URL download ──

    def _sync_public_drive_url(self, url, dest):
        """
        Downloads public/shared Google Drive folder or file links.
        Private/restricted links need a local Drive mount or authenticated integration.
        """
        try:
            import gdown
        except ImportError:
            raise RuntimeError(
                "For Google Drive web URLs, install dependencies:\n"
                "  Run ./install_linux.sh\n"
                "  or: .venv/bin/python -m pip install -r requirements.txt"
            )

        self._send("status", "Checking Google Drive web link…")
        gdown_version = getattr(gdown, "__version__", "unknown")
        self._send("log", f"Web URL mode: gdown {gdown_version}; using installed-API-compatible calls.", "info")
        self._send("log", "Trying public/shared folder, then single-file fallback.", "info")

        staging_root = os.path.join(dest, ".drivesync_download_staging")
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + f"_{threading.get_ident()}"
        temp_root = os.path.join(staging_root, run_id)
        folder_temp = os.path.join(temp_root, "folder_download")
        file_temp = os.path.join(temp_root, "single_file_download")
        os.makedirs(folder_temp, exist_ok=True)
        os.makedirs(file_temp, exist_ok=True)

        # Try folder download first
        folder_result = None
        folder_error = None
        folder_capture = io.StringIO()
        try:
            with contextlib.redirect_stdout(folder_capture), contextlib.redirect_stderr(folder_capture):
                folder_result = call_with_supported_kwargs(
                    gdown.download_folder,
                    url=url, output=folder_temp, quiet=False,
                    use_cookies=False, remaining_ok=True
                )
            captured = folder_capture.getvalue()
            if is_google_quota_error(captured):
                folder_error = captured
                self._send("log",
                    "⚠ Google Drive quota/rate limit detected during folder download. "
                    "Google may block downloads for up to 24 hours.", "warning")
        except Exception as e:
            folder_error = str(e) + "\n" + folder_capture.getvalue()
            if is_google_quota_error(folder_error):
                self._send("log",
                    "⚠ Google Drive quota/rate limit detected. Wait and retry later.", "warning")
            self._send("log", f"Folder download attempt did not succeed: {e}", "warning")

        # Only merge files reported as successfully downloaded by gdown. Files merely
        # present in staging after an interrupted operation are not assumed complete.
        verified_folder_files = []
        if isinstance(folder_result, (list, tuple)):
            for item in folder_result:
                candidate = os.fspath(item)
                if not os.path.isabs(candidate):
                    if os.path.isfile(candidate):
                        candidate = os.path.abspath(candidate)
                    else:
                        candidate = os.path.join(folder_temp, candidate)
                candidate = os.path.abspath(candidate)
                if os.path.isfile(candidate):
                    verified_folder_files.append(candidate)
        elif folder_result:
            # Compatibility fallback for gdown versions that return a truthy non-list.
            for root, _, names in os.walk(folder_temp):
                for name in names:
                    if not name.endswith((".part", ".partial", ".crdownload", ".tmp")):
                        verified_folder_files.append(os.path.join(root, name))

        if verified_folder_files:
            self._send("log", f"Merging {len(verified_folder_files)} verified file(s) from folder download.", "success")
            self._merge_tree(folder_temp, dest, allowed_files=verified_folder_files)
            self._send("progress", 100)
            if folder_result:
                self._send("log", f"Merged {len(verified_folder_files)} gdown-confirmed file(s). Check staging/logs for any missing items.", "success")
                return
            self._send("log", "Folder download returned a partial result; only gdown-confirmed files were merged.", "warning")
        elif folder_result:
            self._send("log", "Google Drive folder result contained no verifiable local files; staging was retained.", "warning")

        # Try single-file download
        for name in os.listdir(file_temp):
            p = os.path.join(file_temp, name)
            try:
                if os.path.isfile(p) or os.path.islink(p):
                    os.remove(p)
                elif os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
            except OSError as e:
                self._send("log", f"Could not clean staging item: {e}", "warning")

        downloaded = None
        single_error = None
        old_cwd = os.getcwd()
        try:
            # gdown chooses a filename from response headers when output=None, so
            # temporarily use the isolated staging directory and always restore cwd.
            os.chdir(file_temp)
            downloaded = call_with_supported_kwargs(
                gdown.download, url=url, output=None, quiet=False, fuzzy=True
            )
        except Exception as e:
            single_error = str(e)
            if is_google_quota_error(single_error):
                self._send("log",
                    "⚠ Google Drive quota/rate limit detected. Wait and retry later (up to 24h).", "warning")
            self._send("log", f"Single-file download attempt did not succeed: {single_error}", "warning")
        finally:
            os.chdir(old_cwd)

        if downloaded:
            candidate = downloaded if os.path.isabs(downloaded) else os.path.join(file_temp, downloaded)
            if os.path.isfile(candidate):
                self._copy_if_needed(candidate, os.path.join(dest, os.path.basename(candidate)))
                self._send("progress", 100)
                return

        # All attempts failed
        if is_google_quota_error(folder_error or ""):
            raise RuntimeError(
                "Google Drive blocked this download (quota/rate limit).\n"
                "Wait and retry later (sometimes up to 24 hours).\n"
                "This is a Google-side limit, not a local issue.\n"
                f"Partial downloads retained at: {temp_root}"
            )
        raise RuntimeError(
            "Could not download this Google Drive URL.\n"
            "• Confirm the link is valid and shared as 'Anyone with the link'.\n"
            "• Private links need a local Drive mount (FUSE/rclone).\n"
            "• If Google reports quota errors, wait and retry later.\n"
            f"Staging data retained at: {temp_root}"
        )

    def _merge_tree(self, src, dest, ignore_dirs=None, allowed_files=None):
        """Merge verified files from a downloaded folder tree into the destination."""
        ignore_dirs = ignore_dirs or set()
        allowed = None if allowed_files is None else {
            os.path.normcase(os.path.abspath(os.fspath(p))) for p in allowed_files
        }
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            rel = os.path.relpath(root, src)
            outroot = dest if rel == "." else os.path.join(dest, rel)
            os.makedirs(outroot, exist_ok=True)
            for name in files:
                if self.stop_event.is_set():
                    return
                if name.endswith((".part", ".partial", ".crdownload", ".tmp")) or name.startswith((".drivesync_part_", ".drivesync_")):
                    self._send("log", f"IGNORED incomplete staging file: {os.path.join(root, name)}", "warning")
                    continue
                sp = os.path.join(root, name)
                if allowed is not None and os.path.normcase(os.path.abspath(sp)) not in allowed:
                    continue
                dp = os.path.join(outroot, name)
                self._copy_if_needed(sp, dp)

    def _walk_error(self, error):
        """Report traversal errors instead of silently skipping inaccessible folders."""
        self.stats.inc_errors()
        self._send("log", f"SCAN ERROR: {error}", "error")

    # ── Local folder sync ──

    def _sync_local(self, source, dest):
        source = os.path.abspath(os.path.expandvars(os.path.expanduser(source)))
        dest = os.path.abspath(os.path.expandvars(os.path.expanduser(dest)))

        # Scan source — skip symlinks to prevent recursive loops
        items = []
        try:
            for root, dirs, files in os.walk(source, followlinks=False, onerror=self._walk_error):
                # Filter out symlinked directories
                dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
                for d in dirs:
                    items.append(("dir", os.path.join(root, d)))
                for f in files:
                    fpath = os.path.join(root, f)
                    # Skip symlinked files (they could point outside the source)
                    if os.path.islink(fpath):
                        if self._is_safe_symlink(fpath, source):
                            items.append(("file", fpath))
                        else:
                            self.stats.inc_skipped()
                            self._send("log", f"SKIPPED (unsafe symlink): {fpath}", "warning")
                    else:
                        items.append(("file", fpath))
        except PermissionError as e:
            self._send("log", f"Permission error scanning source: {e}", "error")
            self.stats.inc_errors()

        total = max(1, len(items))
        self._send("log", f"Scanning local source: {len(items)} items found.", "info")
        self._send("status", f"Syncing {len(items)} items…")

        for idx, (kind, path) in enumerate(items, 1):
            if self.stop_event.is_set():
                self._send("log", "Sync stopped by user.", "warning")
                break

            rel = os.path.relpath(path, source)

            if kind == "dir":
                try:
                    os.makedirs(os.path.join(dest, rel), exist_ok=True)
                except PermissionError as e:
                    self.stats.inc_errors()
                    self._send("log", f"PERMISSION ERROR creating dir: {os.path.join(dest, rel)} | {e}", "error")
            else:
                self._copy_if_needed(path, os.path.join(dest, rel))

            self._send("progress", int(idx * 100 / total))

        self._send("status", "Local folder sync complete.")

    # ── Safe file copy with temp file and hash verification ──

    def _copy_if_needed(self, src, dst):
        """Copy src to dst with temp-file safety and hash-based change detection."""
        try:
            if os.path.isdir(src):
                return

            if is_google_workspace_stub(src):
                self.stats.inc_skipped()
                self._send("log",
                    f"SKIPPED (Google native doc; export from Drive first): {os.path.basename(src)}", "warning")
                return

            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)

            if os.path.exists(dst):
                # Quick check: size difference means definitely changed
                try:
                    src_size = os.path.getsize(src)
                    dst_size = os.path.getsize(dst)
                except OSError:
                    src_size = -1
                    dst_size = -2

                if src_size == dst_size:
                    # Same size — check modification time first (fast), then hash if needed
                    try:
                        # Nanosecond timestamps avoid false skips for same-second edits
                        # on filesystems that expose higher-resolution modification times.
                        src_mtime = os.stat(src).st_mtime_ns
                        dst_mtime = os.stat(dst).st_mtime_ns
                    except OSError:
                        src_mtime = 0
                        dst_mtime = -1

                    if src_mtime == dst_mtime:
                        self.stats.inc_skipped()
                        return

                    # Different mtime but same size — verify with hash
                    src_hash = file_hash(src)
                    dst_hash = file_hash(dst)
                    if src_hash and dst_hash and src_hash == dst_hash:
                        self.stats.inc_skipped()
                        return

                # File needs updating — use temp file for safety
                self._safe_copy(src, dst)
                self.stats.inc_updated()
                self._send("log", f"UPDATED: {os.path.basename(src)}", "success")
                self.retry_queue.remove(src)
                self.retry_queue.save(self._retry_queue_path())
            else:
                # New file — use temp file for safety
                self._safe_copy(src, dst)
                self.stats.inc_copied()
                self._send("log", f"COPIED: {os.path.basename(src)}", "success")
                self.retry_queue.remove(src)
                self.retry_queue.save(self._retry_queue_path())

        except Exception as e:
            self.stats.inc_errors()
            msg = str(e)
            is_quota = is_google_quota_error(msg)

            if is_quota:
                self._send("log",
                    f"FAILED (quota/rate limit; retry later): {os.path.basename(src)} | {msg}", "error")
            elif "Permission" in msg or "denied" in msg.lower():
                self._send("log",
                    f"FAILED (permission denied): {os.path.basename(src)} | {msg}", "error")
            elif "No space" in msg or "ENOSPC" in msg:
                self._send("log",
                    f"FAILED (no disk space): {os.path.basename(src)} | {msg}", "error")
            elif "Input/output error" in msg or "EIO" in msg:
                self._send("log",
                    f"FAILED (I/O error; check if Drive mount is active): {os.path.basename(src)} | {msg}", "error")
            else:
                self._send("log", f"FAILED: {os.path.basename(src)} | {e}", "error")

            self.retry_queue.add(src, dst, msg, is_quota)
            self.retry_queue.save(self._retry_queue_path())

    def _safe_copy(self, src, dst):
        """Stream to a same-directory temporary file, verify it, then atomically replace."""
        def on_progress(done, total, speed, _phase):
            eta = max(0, total - done) / speed if speed > 0 else 0
            speed_mib = speed / (1024 * 1024)
            self._send(
                "status",
                f"Copying {os.path.basename(src)}: {done:,}/{total:,} bytes | "
                f"{speed_mib:.2f} MiB/s | ETA {int(eta)}s"
            )

        def on_retry(attempt, exc):
            self._send(
                "log",
                f"Transient source read failure; retry {attempt}/5 for {os.path.basename(src)}: {exc}",
                "warning"
            )

        result = copy_file_atomic(src, dst, on_progress=on_progress, on_retry=on_retry)
        self._send(
            "log",
            f"Verified transfer: {os.path.basename(src)} ({result['bytes']:,} bytes, "
            f"SHA-256 {result['sha256']})",
            "info"
        )

    # ── Event polling ──

    def _poll_events(self):
        try:
            while True:
                kind, value, tag = self.events.get_nowait()
                if kind == "log":
                    self._log(value, tag)
                elif kind == "status":
                    self.status_var.set(value)
                elif kind == "progress":
                    self.progress_var.set(value)
                elif kind == "done":
                    self.sync_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    if len(self.retry_queue) > 0:
                        self.retry_btn.configure(state="normal")
                    self.status_var.set(
                        "Ready" if not self.schedule_var.get() else "Automatic sync stopped"
                    )
                self.count_label.configure(text=self.stats.summary())
        except queue.Empty:
            pass
        self.root.after(150, self._poll_events)

    # ── Open destination / log ──

    def open_destination(self):
        dest = self.dest_var.get().strip()
        if not dest:
            messagebox.showwarning(APP_NAME, "Enter a destination first.")
            return
        dest = os.path.expandvars(os.path.expanduser(dest))
        if not os.path.isabs(dest):
            dest = os.path.join(self.app_cwd, dest)
        dest = os.path.abspath(dest)
        os.makedirs(dest, exist_ok=True)
        subprocess.Popen(["xdg-open", dest])

    def open_log(self):
        p = self.log_path()
        if not os.path.exists(p):
            messagebox.showinfo(APP_NAME, "No log file yet. Run a sync first.")
            return
        subprocess.Popen(["xdg-open", p])


def main():
    root = tk.Tk()
    DriveSyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
