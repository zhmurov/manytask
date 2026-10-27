import subprocess
import sys


def test_generic_utilities_do_not_import_application_dependencies() -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from importlib.abc import MetaPathFinder
class RejectApplicationImports(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'flask', 'authlib', 'sqlalchemy'}:
            raise AssertionError(f'Generic utilities import {fullname}')
sys.meta_path.insert(0, RejectApplicationImports())
import runpy
utilities = runpy.run_path('manytask/utils/generic.py')
assert utilities['calculate_percent'](1, 2) == 50
assert utilities['lerp']((0, 0), (2, 2), 1) == 1
""",
        ],
        check=True,
    )
