#!/usr/bin/env python3
"""Wrapper for the packaged guest runner."""

from __future__ import annotations

from rally_ci_churn.guest.runner_main import main


if __name__ == "__main__":
    raise SystemExit(main())
