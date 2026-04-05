"""Entry point for `python -m proteomicsviewer` and the `protview` CLI command."""

import sys
from proteomicsviewer.cli import main

if __name__ == "__main__":
    sys.exit(main())
