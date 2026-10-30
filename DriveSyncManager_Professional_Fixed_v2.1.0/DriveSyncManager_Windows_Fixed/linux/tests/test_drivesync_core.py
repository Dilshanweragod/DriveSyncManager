import hashlib
import tempfile
import unittest
from pathlib import Path

from drivesync_core import (
    copy_file_atomic, call_with_supported_kwargs, is_google_quota_error, is_google_workspace_stub,
    is_transient_io_error, paths_overlap,
)

class SimulatedWinTimeout(OSError):
    winerror = 121

class FlakyReader:
    def __init__(self, path):
        self._file = open(path, "rb")
        self._failed = False
    def __enter__(self): return self
    def __exit__(self, *args): self._file.close()
    def seek(self, offset): return self._file.seek(offset)
    def read(self, size=-1):
        if not self._failed:
            self._failed = True
            raise SimulatedWinTimeout("simulated semaphore timeout")
        return self._file.read(size)

class DriveSyncCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.src = self.root / "source.bin"
        self.dst = self.root / "nested" / "destination.bin"
        self.payload = (b"DriveSync reliability test\x00" * 100_000) + b"end"
        self.src.write_bytes(self.payload)
    def tearDown(self): self.temp.cleanup()
    def test_chunked_copy_and_sha256(self):
        result = copy_file_atomic(self.src, self.dst, chunk_size=8192)
        self.assertEqual(self.dst.read_bytes(), self.payload)
        self.assertEqual(result["bytes"], len(self.payload))
        self.assertEqual(result["sha256"], hashlib.sha256(self.payload).hexdigest())
        self.assertFalse(list(self.dst.parent.glob(".drivesync_part_*.tmp")))
    def test_existing_destination_preserved_on_failure(self):
        self.dst.parent.mkdir(parents=True)
        self.dst.write_bytes(b"known-good destination")
        def broken_opener(path, mode): raise PermissionError("simulated source permission failure")
        with self.assertRaises(PermissionError):
            copy_file_atomic(self.src, self.dst, source_opener=broken_opener)
        self.assertEqual(self.dst.read_bytes(), b"known-good destination")
        self.assertFalse(list(self.dst.parent.glob(".drivesync_part_*.tmp")))
    def test_transient_read_error_retried(self):
        retries=[]
        result=copy_file_atomic(self.src, self.dst, chunk_size=4096, base_backoff=0,
            source_opener=lambda path, mode: FlakyReader(path),
            on_retry=lambda attempt, exc: retries.append(attempt))
        self.assertEqual(self.dst.read_bytes(), self.payload)
        self.assertTrue(retries)
        self.assertEqual(result["bytes"], len(self.payload))
    def test_error_classification(self):
        self.assertTrue(is_transient_io_error(SimulatedWinTimeout("timeout")))
        self.assertTrue(is_google_quota_error("Too many users have viewed or downloaded this file recently"))
        self.assertTrue(is_google_quota_error("403 downloadQuotaExceeded"))
        self.assertFalse(is_google_quota_error("Failed to retrieve file URL due to a bad link"))
        self.assertTrue(is_google_quota_error("429 Too Many Requests"))
        self.assertTrue(is_google_workspace_stub("report.gsheet"))
        self.assertFalse(is_google_workspace_stub("video.mp4"))
    def test_dependency_keyword_compatibility(self):
        # Simulate older gdown APIs that do not accept newer optional keywords.
        def old_download_folder(url, output=None, quiet=False, use_cookies=True):
            return {"url": url, "output": output, "quiet": quiet, "use_cookies": use_cookies}
        result = call_with_supported_kwargs(
            old_download_folder, url="https://example.invalid/folder", output="staging",
            quiet=True, use_cookies=False, remaining_ok=True
        )
        self.assertEqual(result["url"], "https://example.invalid/folder")
        self.assertFalse(result["use_cookies"])
        self.assertNotIn("remaining_ok", result)

    def test_path_overlap(self):
        child=self.root / "child"; child.mkdir()
        self.assertTrue(paths_overlap(str(self.root), str(child)))
        self.assertTrue(paths_overlap(str(self.root), str(self.root)))
        unrelated=self.root.parent / (self.root.name + "_other")
        self.assertFalse(paths_overlap(str(self.root), str(unrelated)))

if __name__ == "__main__": unittest.main(verbosity=2)
