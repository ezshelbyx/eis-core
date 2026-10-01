"""E.I.S. Core application entry point.

Run with:  python -m eis.app
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from eis.core.settings import get_settings
        from eis.core.logging_config import setup_logging

        settings = get_settings()
        setup_logging(level=settings.get("logging.level"),
                      console=settings.get("logging.console", True))
        from eis.ui.app import EISApp

        app = EISApp()
        app.mainloop()
        return 0
    except Exception as exc:  # pragma: no cover
        import logging

        logging.getLogger(__name__).exception("Fatal startup error")
        print(f"E.I.S. Core failed to start: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
