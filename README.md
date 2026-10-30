# DriveSync Manager

Cross-platform folder synchronization and Google Drive download manager for Windows and Linux.

## Project status

This GitHub repository has been initialized with the project documentation, contribution guidance, issue templates, and QA notes. The application source directories and automated test files from the prepared v2.1.1 package have **not yet been committed**. The repository is therefore not yet a runnable application checkout.

## Intended capabilities in the prepared package

- Copy files between local folders and mounted Google Drive folders.
- Download files from public/shared Google Drive links using `gdown`.

## Known limitations

- OAuth 2.0 authenticated Google Drive API integration is not included.
- Google Workspace document export through the API is not included.
- Uploading files to Google Drive is not included.

## Documentation

- [Installation](docs/INSTALLATION.md)
- [Technical specification](docs/TECHNICAL_SPECIFICATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [QA report](QA_REPORT.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

## Testing

The prepared package's Windows and Linux source test suites each passed 8 tests in the available Linux environment. Native Windows, DriveFS, and live Google Drive integration acceptance testing remain outstanding. The CI workflow will be enabled after the application source and test directories are committed.

## License

No license has been selected yet. All rights remain with the respective copyright holder until a license is added.
