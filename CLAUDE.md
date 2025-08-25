# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development

1.  After cloning the repository, set up the environment with: `uv sync`.
2.  Install browser drivers with: `playwright install`.

## Commands

*   **Run tests:** `python run_tests.py` in root, or run `pytest`.
    *   Specific test categories can be run by passing the category as an argument, eg. `python run_tests.py unit`.
*   **Lint:** No lint command found. Consider adding ruff or similar to pyproject.toml.
*   **Build:** No explicit build command found.

## Architecture

The project uses a plugin-based architecture. Key aspects:

*   `main.py`: Entry point for the application.
*   `cli/cli_ieee.py`: Implements the `ieee` plugin for interacting with IEEE websites using Playwright.
*   `utils`: Provides utility functions.
*   `cache`: Handles caching of data.
*   `filters`: Modules for creating and applying filters to JSON data.
*   `T.py`: Defines data structures.

## Usage

The `ieee` plugin can be used to:

*   Download publication information.
*   Download author information, including lists of publications.

See the `README.md` file for examples.