"""
JARVIS Controller — root-level launcher.

This file ensures you can run:

    python jarvis_controller.py

from the project root (C:\\Users\\admin\\jarvis-ai) and it will
correctly invoke the real controller located in assistant\\.
"""

import os
import sys

# Ensure the assistant\ directory is on sys.path so the controller
# can import its own sibling modules if needed in the future.
_here = os.path.dirname(os.path.abspath(__file__))
_assistant_dir = os.path.join(_here, "assistant")

if _assistant_dir not in sys.path:
    sys.path.insert(0, _assistant_dir)

# Execute the real controller as __main__.
import runpy
runpy.run_path(
    os.path.join(_assistant_dir, "jarvis_controller.py"),
    run_name="__main__",
)
