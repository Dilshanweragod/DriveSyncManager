# Technical Specification

## Overview

DriveSync Manager is a Python desktop application with Tkinter interfaces and shared synchronization helpers. Separate Windows and Linux entry points provide platform-specific integration while sharing core transfer logic.

## Current capabilities

- Local folder and mounted Google Drive folder file copying.
- Public/shared Google Drive link downloading through `gdown`.
- Chunked copying and SHA-256 verification in core transfer operations.
- Retry handling and staging/merge behavior covered by unit tests.

## Layout

- `windows/`: Windows UI, core module, batch installer/launcher, requirements, and tests.
- `linux/`: Linux UI, core module, shell installer/launcher, desktop entry, requirements, and tests.
- `docs/`: installation, troubleshooting, and this specification.

## Exclusions

OAuth 2.0 authenticated Google Drive API access, Workspace document export through the API, and uploading files to Google Drive are not implemented.

## Validation

The Windows and Linux source test suites each passed 8 tests when executed in the available Linux environment. This is not native Windows or live DriveFS integration testing.