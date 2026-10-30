# DriveSync Manager v2.1.1 — Windows Edition

Python/Tkinter desktop application for copying and updating files from local folders, mounted Google Drive folders, and public/shared Google Drive web links.

## Reliability improvements

- **Chunked streaming:** copies in 1 MiB chunks instead of `shutil.copy2`, reducing large-file I/O pressure.
- **Bounded transient retries:** retries recognized transient source read errors, including Windows semaphore timeout (`WinError 121`) and insufficient-resource (`WinError 1450`) failures, with exponential backoff.
- **Atomic destination update:** writes to a temporary file beside the destination, verifies byte count and source stability, then atomically replaces the destination. Existing destination data is preserved if a transfer fails.
- **SHA-256 transfer digest:** records a digest for each completed file; source/destination size and timestamp checks are used for change detection.
- **Correct file classification:** only known Google Workspace shortcut extensions are treated as native-document stubs. `WinError 1` on an ordinary `.mp4`, `.pdf`, `.cdr`, `.zip`, or other file is reported as an I/O/filesystem issue, not mislabelled as a Workspace document.
- **Persistent retry queue:** failed file operations are saved atomically in `.drivesync_retry_queue.json`; automatic retries avoid quota-blocked items, while manual retry can try them again later.
- **Safer public-link staging:** each URL run gets a separate staging directory; partial/temp files are not merged as completed files. gdown calls now filter optional keyword arguments against the installed function signature, fixing compatibility errors for `remaining_ok` and `fuzzy`.
- **Log rotation:** the log is rotated after it grows beyond approximately 2 MiB.
- **Path overlap protection:** source and destination cannot be identical or nested within one another.
- **Traversal diagnostics:** inaccessible source folders are reported rather than silently ignored.
- **Live file transfer status:** reports bytes, throughput and estimated remaining time for local/mounted file copies.

## Install

### Windows
1. Install Python 3.11+ from https://www.python.org/downloads/windows/ and enable the Python Launcher.
2. Extract this folder to a writable location.
3. Run `Install_DriveSyncManager.bat`, then `Run_DriveSyncManager.bat`.

### Linux
On Ubuntu/Debian, install `python3`, `python3-venv`, and `python3-tk`, then run `./install_linux.sh` and `./run_linux.sh`.

## Usage

1. Set **Source** to a local/mounted folder or a public/shared Google Drive URL.
2. Set **Destination** to a different folder.
3. Click **Sync now**. Optional scheduled sync repeats while the app stays open.
4. Use **Retry failed** after resolving a local issue or when Google quota limits may have cleared.

Destination-only files are retained; this app does not delete destination files to mirror source deletions. Keep private/restricted Google Drive files on a mounted Drive path, or use an authenticated API client outside this build.

## Known limitations

- Google Drive quota/rate limits are imposed by Google and cannot be bypassed. Wait, then retry, or ask the owner for a fresh copy.
- Google Workspace shortcut files (`.gdoc`, `.gsheet`, `.gslides`, `.gdraw`, `.gform`, `.gmap`, `.gsite`) are references, not the actual document content. Export/download them from Google Drive first.
- This build does **not** implement authenticated Google Drive API OAuth, cloud-native document export, or upload-to-Drive. These features need a separate API module and Google Cloud OAuth configuration.
- A chunked transfer engine improves resilience but cannot guarantee recovery if a virtual Drive mount disconnects or Windows continues to reject reads. In that case the file is queued and the source/mount must become available again.
- This is a Python source package, not a compiled `.exe` or Linux binary. Tkinter and a desktop environment are required.
- Logs include local paths; review them before sharing.

## Troubleshooting

- **Python/Tkinter missing:** install Python and Tkinter for your OS, then rerun the installer.
- **`No module named gdown`:** rerun the installer.
- **`WinError 121` / `WinError 1450`:** the app retries transient reads; if it still fails, confirm Drive for desktop is running, make the file available offline, and retry.
- **`WinError 1: Incorrect function`:** the app no longer assumes this means a Google Workspace document. Check whether the mounted filesystem supports the requested read and retry after the file is available locally.
- **Google download quota:** wait for the provider limit to clear; the app cannot bypass it.
- **Permission or disk-space errors:** verify source read access, destination write access and free space.

## Tests

From this platform folder, run:

```bash
python -m unittest discover -s tests -v
```
