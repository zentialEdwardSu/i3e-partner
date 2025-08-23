"""Global pytest configuration and fixtures"""

import pytest
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def temp_directory():
    """Create a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def clean_temp_dir(temp_directory):
    """Provide a clean temporary directory for each test"""
    test_dir = os.path.join(temp_directory, "test_specific")
    os.makedirs(test_dir, exist_ok=True)
    yield test_dir
    # Cleanup happens automatically with session fixture


@pytest.fixture
def mock_logger():
    """Mock logger fixture"""
    from unittest.mock import MagicMock

    return MagicMock()


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically"""
    for item in items:
        # Add unit marker to all tests by default
        if not any(
            marker.name in ["integration", "slow"] for marker in item.iter_markers()
        ):
            item.add_marker(pytest.mark.unit)
