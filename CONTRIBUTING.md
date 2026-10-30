# Contributing

Thank you for considering a contribution.

1. Open an issue before substantial changes so the scope can be discussed.
2. Keep Windows and Linux behavior aligned where practical.
3. Add or update unit tests for bug fixes and new core behavior.
4. Run both test suites before submitting a pull request:
   - `python -m unittest discover -s windows/tests -v`
   - `python -m unittest discover -s linux/tests -v`
5. Describe the tested operating system and Python version in the pull request.
6. Never commit credentials, Google Drive tokens, private files, or local environment folders.

Pull requests should explain the problem, the change, and remaining limitations.