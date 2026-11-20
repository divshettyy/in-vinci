# Contributing

Thanks for taking the time to contribute.

## Reporting bugs

Open an issue using the **Bug report** template. Include:
- Steps to reproduce
- Expected vs actual behaviour
- Python version and OS
- Relevant error output (redact any personal data)

## Suggesting features

Open an issue using the **Feature request** template before writing any code.

## Pull requests

1. Fork the repo and create a branch from `main` / `master`
2. Install dev dependencies: `pip install -r requirements-dev.txt` (if present) or `pip install pytest flake8`
3. Make your change with a clear commit message
4. Run tests: `pytest -q`
5. Open a pull request — describe the problem and solution

## Code style

- PEP 8, max line length 120
- No new hard external dependencies unless discussed first
- Keep changes focused — one fix or feature per PR

## Authorized use

This project is for personal/authorized use only. Do not submit changes that add functionality targeting systems without permission.
