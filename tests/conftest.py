"""Pytest configuration for daf_okn tests."""

import os

# Force the headless matplotlib backend before anything imports pyplot.
os.environ.setdefault("MPLBACKEND", "Agg")
