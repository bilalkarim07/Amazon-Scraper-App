"""
BackEnd/main.py — Convenience entry point.

You can start the server with either:
    uv run uvicorn application.main:app --reload --port 8000
or:
    uv run python main.py
"""

import uvicorn


def main():
    uvicorn.run(
        "application.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
