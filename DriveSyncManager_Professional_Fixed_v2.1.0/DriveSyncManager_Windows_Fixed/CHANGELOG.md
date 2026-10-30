# Changelog

## 2.1.1 — 2026-10-30
- Fixed public/shared Drive folder download compatibility when installed `gdown` does not support the `remaining_ok` keyword.
- Fixed single-file fallback compatibility when installed `gdown` does not support the `fuzzy` keyword.
- Added a regression test for filtering unsupported optional dependency arguments.
- Logged the detected gdown version for easier troubleshooting.
- Included folder and single-file failure details in the final error message.
- Clarified that mounted Google Workspace shortcut files remain non-content stubs and require an authenticated Drive API export feature, which is not included in this build.

## v2.1.0 — Reliability update

- Replaced `shutil.copy2()` transfer path with bounded 1 MiB streaming reads.
- Added bounded exponential-backoff retries for transient read errors.
- Added same-directory temporary writes, byte-count verification, source-stability checks, SHA-256 transfer digest, and atomic replacement.
- Preserved existing destination files when transfer fails.
- Corrected quota classification so generic failed-URL messages are not automatically called quota errors.
- Corrected the `WinError 1` classification so ordinary binary files are not mislabeled as Google Workspace documents.
- Fixed component-safe source/destination overlap detection.
- Fixed persistent retry queue loading/saving and manual retry of quota-blocked items.
- Made retry queue saves atomic and added log rotation.
- Added per-run URL staging directories and restricted folder merging to files reported by gdown as downloaded; partial/temp files are excluded.
- Added scan-error reporting, live local-file speed/ETA, and automated tests.

## Known exclusions

- OAuth 2.0 authenticated Google Drive API integration is not included.
- Google Workspace document export through the API is not included.
- Upload-to-Drive and resumable cloud upload are not included.
- Actual Google Drive quota bypass is not possible; quota locks must clear at Google's side.
