import tempfile
import unittest
from pathlib import Path
from DriveSyncManager import RetryQueue

class RetryQueueTests(unittest.TestCase):
    def test_persistence_and_manual_quota_retry(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / ".drivesync_retry_queue.json")
            q = RetryQueue()
            q.add("src.mp4", "dst.mp4", "quota exceeded", is_quota=True)
            q.save(path)
            loaded = RetryQueue()
            loaded.load(path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded.get_retryable(), [])
            self.assertEqual(len(loaded.get_retryable(include_quota=True, force=True)), 1)
            loaded.remove("src.mp4")
            loaded.save(path)
            again = RetryQueue(); again.load(path)
            self.assertEqual(len(again), 0)

if __name__ == "__main__": unittest.main(verbosity=2)
