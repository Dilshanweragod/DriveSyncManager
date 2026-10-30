# DriveSync Manager v2.1.1 — QA Report

## Scope reviewed

The supplied `DriveSyncManager_Windows_Fixed.rar` source tree was inspected. The Windows and Linux app sources were updated, and a shared transfer-core implementation was added to each platform directory.

## Changes applied

12. gdown compatibility adapter now filters optional keyword arguments against the installed function signatures, preventing `remaining_ok` and `fuzzy` TypeErrors on older or variant releases.
14. Failed public URL downloads now include the actual folder and single-file attempt errors in the final diagnostic message.
13. The detected gdown version is written to the activity log.

1. Chunked file transfer (default 1 MiB) replaces `shutil.copy2()` for the actual file-copy path.
2. Transient source-read failures are retried with capped exponential backoff (up to five retries per chunk).
3. Data is written to a temporary file in the destination directory; size and source stability are checked before `os.replace()` commits it.
4. Existing destination content is not replaced when the transfer fails.
5. SHA-256 is computed for completed transfers and recorded in the activity log.
6. Google Workspace shortcut detection is extension-specific; ordinary binary files are no longer labeled Workspace documents merely because an I/O error says `WinError 1`. Native `.gdoc`/`.gsheet`/`.gslides` shortcut stubs are still skipped because authenticated Google Drive API export is not implemented in this release.
7. Quota classification was tightened; a generic failed URL retrieval is no longer automatically treated as a quota lock.
8. Source/destination overlap uses normalized real paths and path-component-safe `commonpath` checks.
9. Retry queue load/save behavior was repaired; queue persistence is atomic, and manual retries can include quota-blocked or previously exhausted entries.
10. Public-link staging is unique per attempt, and only gdown-reported files are merged from folder downloads. Known partial/temp suffixes are excluded.
11. Added log rotation, source traversal error reporting, and local-copy speed/ETA status.

## Automated checks executed

The following checks were run in this Linux build environment for **both** the Windows and Linux source folders:

- Python bytecode compilation (`py_compile`) — passed.
- Chunked copy and SHA-256 digest test — passed.
- Transient `WinError 121` retry simulation — passed.
- Transient `WinError 1450` classification test — passed.
- Existing destination preserved after a simulated copy failure — passed.
- Google quota and Workspace extension classification — passed.
- Source/destination path overlap test — passed.
- Merge only verified staging files and ignore `.part` files — passed.
- Persistent retry queue round-trip and manual quota retry behavior — passed.

Result: **8 automated tests passed per platform folder** in the available test environment, including a regression test for gdown API keyword compatibility.

## What was not verified

- This environment is Linux, so the app was not executed on a real Windows host or against the Windows Google Drive for Desktop/DriveFS virtual filesystem. Actual `WinError 121` and `1450` recovery still needs a Windows integration test with your affected large MP4 files.
- No live public Google Drive URL download was run; network access, file permissions, gdown behavior, and provider quota responses were not end-to-end tested.
- Tkinter GUI interaction was not tested in a graphical desktop session.
- Automated unit tests validate the transfer core and queue logic, not every possible filesystem driver or network state.

## Features not implemented in this build

This source package still does **not** implement authenticated Google Drive API OAuth, Google Workspace document export via the API, or upload/resumable upload to Drive. The current implementation supports local/mounted-folder copies and public/shared Google Drive web links. Those API features need a separate implementation and Google Cloud OAuth credentials; they should not be considered available based on this build.

## Recommended real-machine acceptance test

1. Install the Windows build with Python 3.11+ and run `Install_DriveSyncManager.bat`.
2. Copy one small file, one 1–5 GB video, and a directory containing mixed file types from the mounted Drive to a separate local destination.
3. Confirm the SHA-256 completion log appears for successful files and that existing destination files remain intact if a source read fails.
4. Test an online-only file, an unavailable source, a restricted public link, and a quota-blocked public link.
5. Close and reopen the app after a failed file; confirm the retry queue persists and the manual retry action works.
6. Compare source and destination sizes and, for critical files, compute independent hashes after transfer.
