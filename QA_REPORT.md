# QA Report — DriveSync Manager 2.1.1

## Automated tests

The Windows source test suite completed successfully in the available Linux environment: 8 tests passed.

The Linux source test suite completed successfully in the available Linux environment: 8 tests passed.

Coverage includes chunked copying and SHA-256, dependency keyword compatibility, error classification, destination preservation after failed transfers, path overlap, transient read retry, verified staging merge and partial-file exclusion, and retry queue persistence/manual quota retry.

## Environment limitations

- Tests were executed in a Linux environment only.
- Native Windows desktop behavior has not been acceptance-tested in this run.
- Google Drive for Desktop / DriveFS integration has not been live-tested.
- Public Google Drive network downloads have not been live-tested.
- GUI workflows have not received automated end-to-end testing.

## Conclusion

The included automated unit tests pass in the available environment. This report does not claim native Windows or live Google Drive integration validation.