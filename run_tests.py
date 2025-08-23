#!/usr/bin/env python3
"""Test runner script for objfilter and related modules using pytest"""

import sys
import subprocess
from pathlib import Path


def run_tests():
    """Run all tests using pytest"""
    project_root = Path(__file__).parent

    # Basic pytest command
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(project_root / "tests"),
        "-v",
        "--tb=short",
    ]

    # Add coverage if pytest-cov is available
    try:
        import pytest_cov

        cmd.extend(
            [
                "--cov=utils",
                "--cov=cli",
                "--cov-report=term-missing",
                "--cov-report=html:htmlcov",
            ]
        )
        print("Running tests with coverage...")
    except ImportError:
        print(
            "Running tests without coverage (install pytest-cov for coverage reports)..."
        )

    # Run pytest
    try:
        result = subprocess.run(cmd, cwd=project_root)
        return result.returncode
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1


def run_specific_tests():
    """Run specific test categories"""
    project_root = Path(__file__).parent

    if len(sys.argv) > 1:
        test_type = sys.argv[1]

        cmd = [sys.executable, "-m", "pytest", str(project_root / "tests"), "-v"]

        if test_type == "unit":
            cmd.extend(["-m", "unit"])
        elif test_type == "integration":
            cmd.extend(["-m", "integration"])
        elif test_type == "slow":
            cmd.extend(["-m", "slow"])
        elif test_type == "fast":
            cmd.extend(["-m", "not slow"])
        else:
            print(f"Unknown test type: {test_type}")
            print("Available types: unit, integration, slow, fast")
            return 1

        try:
            result = subprocess.run(cmd, cwd=project_root)
            return result.returncode
        except Exception as e:
            print(f"Error running tests: {e}")
            return 1
    else:
        return run_tests()


if __name__ == "__main__":
    sys.exit(run_specific_tests())
