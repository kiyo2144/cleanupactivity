"""WSGI entry point for production deployments."""

from pathlib import Path

from dotenv import load_dotenv

from hiromachi import create_app


project_dir = Path(__file__).resolve().parent
load_dotenv(project_dir / ".env")

application = create_app()
