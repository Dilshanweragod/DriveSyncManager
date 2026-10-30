import tempfile
import threading
import unittest
from pathlib import Path
from DriveSyncManager import DriveSyncApp

class MergeStagingTests(unittest.TestCase):
    def test_only_verified_files_are_merged_and_partial_files_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); source=root/"staging"; dest=root/"dest"
            source.mkdir(); dest.mkdir()
            good=source/"good.bin"; good.write_bytes(b"complete")
            unverified=source/"unverified.bin"; unverified.write_bytes(b"maybe partial")
            partial=source/"incomplete.bin.part"; partial.write_bytes(b"partial")
            app=DriveSyncApp.__new__(DriveSyncApp)
            app.stop_event=threading.Event()
            app._send=lambda *args, **kwargs: None
            copied=[]
            app._copy_if_needed=lambda src, dst: copied.append((Path(src).name, Path(dst).name))
            app._merge_tree(str(source), str(dest), allowed_files=[str(good)])
            self.assertEqual(copied, [("good.bin", "good.bin")])

if __name__ == "__main__": unittest.main(verbosity=2)
