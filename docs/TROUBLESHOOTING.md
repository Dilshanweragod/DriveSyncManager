# Troubleshooting

## Public/shared Google Drive links

Confirm that the link is accessible with its sharing permissions. Check that the installed `gdown` version is compatible; the package requirement is `gdown>=5.2.0`. Google Drive download quotas and permission restrictions cannot be bypassed.

## Google Drive for Desktop / DriveFS

Mounted Drive paths are managed by Google Drive for Desktop. Intermittent I/O failures, unavailable cloud-only files, or virtual-drive timeouts may originate in DriveFS, network conditions, or local system resources. Confirm Drive for Desktop is running and that the file is available offline where appropriate.

## Workspace shortcut files

`.gdoc`, `.gsheet`, and `.gslides` can be reference stubs rather than ordinary document contents. This build does not use the authenticated Google Drive API to export them.

## Windows shortcuts

A message that `pywin32` is unavailable and PowerShell is being used for `.lnk` handling is a fallback notice, not necessarily a fatal error.

## Transfer errors

WinError 1450, 121, or 1 can occur during virtual-drive I/O. The precise cause depends on the environment. Check DriveFS status, connectivity, available resources, and whether the source can be read outside the application.