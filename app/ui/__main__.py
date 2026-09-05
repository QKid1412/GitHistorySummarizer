"""`python -m app.ui` — start the local report builder."""

from __future__ import annotations

import argparse

from app.ui.server import DEFAULT_PORT, serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.ui",
        description="Start the local report builder UI. Binds to 127.0.0.1 only.",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to listen on (default {DEFAULT_PORT}).")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser automatically.")
    args = parser.parse_args(argv)

    try:
        return serve(port=args.port, open_browser=not args.no_browser)
    except OSError as error:
        print(f"Could not start on port {args.port}: {error}")
        print("Another process is probably using it. Try --port 8766.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
