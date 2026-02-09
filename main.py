#!/usr/bin/env python3
"""
GOrchestrator - Intelligent AI Agent Manager.

This is the main CLI entry point. GOrchestrator is a conversational
"Architect Agent" that communicates with users and delegates coding
tasks to the Worker Agent (Mini-SWE-GOCore).
"""

import io
import logging
import sys
from pathlib import Path


def configure_encoding():
    """
    Force UTF-8 encoding on Windows to prevent charmap errors.
    Must be called before any output is written.
    """
    if sys.platform == "win32":
        # Reconfigure stdout and stderr to use UTF-8
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        else:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )

        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        else:
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace"
            )

        # Also set environment variable for child processes
        import os
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")


# Configure encoding FIRST, before any imports that might print
configure_encoding()

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core import SessionEngine, get_settings


def main():
    """Main entry point - start interactive session with Manager Agent."""
    # Configure logging - file only, no console noise
    log_dir = Path(__file__).parent / ".gorchestrator"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "gorchestrator.log", encoding="utf-8"),
        ],
    )
    # Suppress noisy third-party loggers
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    try:
        settings = get_settings()
        engine = SessionEngine(settings=settings)
        engine.start_interactive_mode()
        return 0

    except KeyboardInterrupt:
        print("\nGoodbye!")
        return 130
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
