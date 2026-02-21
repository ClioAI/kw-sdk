#!/usr/bin/env python3
"""Build standalone verif binary using PyInstaller."""

import subprocess
import sys

subprocess.run(
    [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "verif",
        "--hidden-import", "verif",
        "--hidden-import", "verif.providers.gemini",
        "--hidden-import", "verif.providers.openai",
        "--hidden-import", "verif.providers.anthropic",
        "cli.py",
    ],
    check=True,
)
print("\nBuild complete: dist/verif")
