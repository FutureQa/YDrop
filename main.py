"""
YDrop — Entry point.

Launches the CustomTkinter application window.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path when running from source
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from ui.app import YDropApp


def main() -> None:
    app = YDropApp()
    app.mainloop()


if __name__ == "__main__":
    main()
