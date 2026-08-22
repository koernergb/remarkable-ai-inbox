"""Allow the package to run with ``python -m app``."""

from app.cli import app

if __name__ == "__main__":
    app()
