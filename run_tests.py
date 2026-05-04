#!/usr/bin/env python3
"""
Test runner script for the Open Mic Odyssey project.

This script runs the test suite using pytest and provides
convenient options for different test scenarios.
"""

import subprocess
import sys
from pathlib import Path


def run_tests(test_type="all", verbose=False, coverage=False):
    """Run the test suite with specified options."""

    cmd = [sys.executable, "-m", "pytest"]

    if test_type == "unit":
        cmd.extend(["-m", "not integration"])
    elif test_type == "integration":
        cmd.extend(["-m", "integration"])
    elif test_type == "app":
        cmd.extend(["tests/test_app.py"])
    elif test_type == "static":
        cmd.extend(["tests/test_static_generator.py"])
    elif test_type == "schema":
        cmd.extend(["tests/test_schema.py"])

    if verbose:
        cmd.append("-v")
    else:
        cmd.append("--tb=short")

    if coverage:
        cmd.extend([
            "--cov=website",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)

    return result.returncode


def main():
    """Main entry point for the test runner."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run tests for Open Mic Odyssey")
    parser.add_argument(
        "test_type",
        choices=["all", "unit", "integration", "app", "static", "schema"],
        default="all",
        nargs="?",
        help="Type of tests to run"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )

    args = parser.parse_args()

    exit_code = run_tests(
        test_type=args.test_type,
        verbose=args.verbose,
        coverage=args.coverage
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
