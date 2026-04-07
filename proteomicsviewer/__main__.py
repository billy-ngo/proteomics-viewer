"""
Entry point for `python -m proteomicsviewer` and the `proker` CLI command.

Starts the FastAPI server, serves the bundled frontend, and opens the browser.
"""

import sys

# Set Windows event loop policy as early as possible to prevent
# ProactorEventLoop socket errors (WinError 64)
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from proteomicsviewer.cli import main

if __name__ == "__main__":
    sys.exit(main())
