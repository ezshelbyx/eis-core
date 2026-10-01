"""Convenience entry point:  python __main__.py  (delegates to eis.app)."""

from eis.app import main

if __name__ == "__main__":
    raise SystemExit(main())
