# DriveSync Manager

Cross-platform folder synchronization and Google Drive download manager for Windows and Linux.

## Project package

The complete source package is prepared as `DriveSyncManager_Complete_v2.1.1.zip`. This repository is being initialized with the project documentation and supporting files.

## Supported workflows

- Copy files between local folders and mounted Google Drive folders.
- Download files from public/shared Google Drive links using `gdown`.

## Limitations

- OAuth 2.0 authenticated Google Drive API integration is not included.
- Google Workspace document export through the API is not included.
- Uploading files to Google Drive is not included.

## Testing status

The included automated Windows and Linux source test suites each passed 8 tests in the available Linux environment. Native Windows, Google Drive for Desktop/DriveFS, and live Google Drive network acceptance testing remain outstanding.

## Documentation

See `docs/INSTALLATION.md`, `docs/TECHNICAL_SPECIFICATION.md`, `docs/TROUBLESHOOTING.md`, `CHANGELOG.md`, and `QA_REPORT.md`.

## License

No license has been selected yet. All rights remain with the respective copyright holder until a license is added.
