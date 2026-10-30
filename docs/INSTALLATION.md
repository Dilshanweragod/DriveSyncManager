# Installation

## Windows

1. Install Python 3.11 or 3.12 and enable the option to add Python to PATH.
2. Open the `windows` directory.
3. Run `Install_DriveSyncManager.bat`.
4. Start the application with `Run_DriveSyncManager.bat`.

## Linux

1. Install Python 3.11 or 3.12, Tkinter, and required system packages.
2. Open a terminal in the `linux` directory.
3. Run `chmod +x install_linux.sh run_linux.sh`.
4. Run `./install_linux.sh`, then `./run_linux.sh`.

## Dependencies

Install Python dependencies with `python -m pip install -r requirements.txt` from the platform directory. The current dependency list includes `gdown>=5.2.0`.

Google Drive for Desktop must be installed and signed in separately to access a mounted Drive folder. Public/shared link downloading requires network access and valid sharing permissions.