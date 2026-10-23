"""Runs the assertion-style check scripts in tests/scripts/ under pytest.

Each script is a sequence of module-level asserts; any failure fails its test.
"""
import runpy
from pathlib import Path

import pytest

SCRIPTS = sorted((Path(__file__).parent / "scripts").glob("*_checks.py"))


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.stem)
def test_check_script(script):
    runpy.run_path(str(script), run_name="__main__")
