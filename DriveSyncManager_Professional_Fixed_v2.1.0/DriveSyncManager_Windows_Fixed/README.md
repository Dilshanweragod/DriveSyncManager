# DriveSync Manager v2.1.1 — Reliability Update

Choose the platform folder:

## Windows
1. Extract the ZIP to a writable folder.
2. Open `windows` and double-click `Install_DriveSyncManager.bat`.
3. Double-click `Run_DriveSyncManager.bat`.

## Linux (Ubuntu/Debian)
1. Open a terminal in the `linux` folder.
2. Install prerequisites if needed: `sudo apt install python3 python3-venv python3-tk`.
3. Run `chmod +x install_linux.sh run_linux.sh`.
4. Run `./install_linux.sh`, then `./run_linux.sh`.

This source package supports local/mounted-folder copying and public/shared Google Drive links. It does **not** yet include authenticated Google Drive API OAuth, Workspace document export, or upload-to-Drive. Those features require a separate implementation and Google Cloud credentials; they are not advertised as available in this build.
