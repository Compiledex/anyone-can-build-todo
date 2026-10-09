"""A test runner that sorts the tests into layers: CUJ, integration and unit.

The folder a test is in is its layer: `.../tests/unit/`, `.../tests/integration/`
or `.../tests/cuj/`. The runner refuses tests that break the rules for their
layer, and prints one line per layer at the end of the run.
"""

import os
import re
import sys
import unittest
import warnings
from collections import Counter, defaultdict

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import SimpleTestCase, TransactionTestCase
from django.test.runner import DiscoverRunner, ParallelTestSuite
from django.test.utils import iter_test_cases

# Top of the pyramid first, the order the summary prints them in.
LAYERS = {"cuj": "CUJ", "integration": "Integration", "unit": "Unit"}
LAYER_IN_ID = re.compile(r"\btests\.(cuj|integration|unit)\.")


class TestLayerError(Exception):
    pass


def layer_of(test_id):
    """The layer a test is in, from its id, or None if it is in no layer folder.

    The id also works for an error in setUpClass, which unittest reports as
    "setUpClass (todos.tests.cuj.test_journeys.SomeTests)".
    """
    match = LAYER_IN_ID.search(test_id)
    return match.group(1) if match else None


def check_layers(tests):
    """Raise TestLayerError if any test breaks the rules for its layer."""
    problems = []
    for test in tests:
        if type(test).__module__ == "unittest.loader":
            continue  # A test file that failed to import. Let that error show.
        layer = layer_of(test.id())
        if layer is None:
            problems.append(
                f"{test.id()} is not in a unit/, integration/ or cuj/ folder."
            )
        elif layer == "unit" and (
            not isinstance(test, SimpleTestCase)
            or isinstance(test, TransactionTestCase)
        ):
            problems.append(
                f"{test.id()} is a unit test, so it must be a SimpleTestCase."
            )
        elif layer == "cuj" and not isinstance(test, StaticLiveServerTestCase):
            problems.append(
                f"{test.id()} is a CUJ test, so it must be a StaticLiveServerTestCase."
            )
    if problems:
        raise TestLayerError(
            "Some tests break the layer rules:\n  " + "\n  ".join(problems)
        )


class LayerCounter:
    """Counts passes, failures, errors and skips for each layer.

    With --parallel, Django sends every result from the worker processes back
    to this result in the main process, so the counts include every worker.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.layer_counts = defaultdict(Counter)

    def _count(self, test, outcome):
        self.layer_counts[layer_of(test.id())][outcome] += 1

    def addSuccess(self, test):
        super().addSuccess(test)
        self._count(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._count(test, "failed")

    def addError(self, test, err):
        super().addError(test, err)
        self._count(test, "errors")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._count(test, "skipped")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._count(test, "passed")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._count(test, "failed")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            failed = issubclass(err[0], test.failureException)
            self._count(test, "failed" if failed else "errors")


class LayeredTestResult(LayerCounter, unittest.TextTestResult):
    pass


def format_summary(layer_counts):
    lines = ["Test layers"]
    names = {**LAYERS, None: "No layer"}
    layers = list(LAYERS) + ([None] if None in layer_counts else [])
    for layer in layers:
        counts = layer_counts.get(layer)
        if not counts:
            lines.append(f"  {names[layer]:<12} no tests")
            continue
        parts = [f"{counts.get('passed', 0):>2} passed"]
        if counts.get("failed"):
            parts.append(f"{counts['failed']} failed")
        if counts.get("errors"):
            parts.append(
                f"{counts['errors']} error" + ("s" if counts["errors"] > 1 else "")
            )
        if counts.get("skipped"):
            parts.append(f"{counts['skipped']} skipped")
        lines.append(f"  {names[layer]:<12} " + ", ".join(parts))
    return "\n".join(lines)


def ignore_missing_static_root():
    """Hide WhiteNoise's warning that the STATIC_ROOT folder does not exist.

    Only `collectstatic` makes that folder, on a live server. The tests do not
    need it, so the warning only adds noise. A missing folder anywhere else
    still warns.
    """
    folder = os.path.join(settings.STATIC_ROOT, "")  # WhiteNoise ends it with a "/".
    warnings.filterwarnings(
        "ignore", message=re.escape(f"No directory at: {folder}") + "$"
    )


class LayeredParallelTestSuite(ParallelTestSuite):
    # With --parallel on macOS, each test process starts a fresh Python, which
    # does not keep the warning filters. Django calls this in each process.
    process_setup = ignore_missing_static_root


class LayeredTestRunner(DiscoverRunner):
    parallel_test_suite = LayeredParallelTestSuite

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        ignore_missing_static_root()

    def build_suite(self, *args, **kwargs):
        suite = super().build_suite(*args, **kwargs)
        check_layers(iter_test_cases(suite))
        return suite

    def get_resultclass(self):
        base = super().get_resultclass()
        if base is None:
            return LayeredTestResult
        # --debug-sql and --pdb use their own result class. Count on top of it.
        return type(f"Layered{base.__name__}", (LayerCounter, base), {})

    def run_suite(self, suite, **kwargs):
        result = super().run_suite(suite, **kwargs)
        print("\n" + format_summary(result.layer_counts), file=sys.stderr)
        return result
