import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hydrohome.container import build_services  # noqa: E402


@pytest.fixture
def services(tmp_path):
    return build_services(tmp_path / "test.db")


@pytest.fixture
def household(services):
    return services.households.add({"name": "Cruz", "address": "Rizal St", "city": "Tarlac City",
                                    "members": "4", "daily_target_liters": "100"})
