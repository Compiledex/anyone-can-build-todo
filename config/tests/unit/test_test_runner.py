import io

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import SimpleTestCase, TestCase

from config.test_runner import (
    LayeredTestResult,
    TestLayerError,
    check_layers,
    format_summary,
    layer_of,
)


def make_test(module, base=SimpleTestCase):
    """One test case whose id says it lives in `module`."""
    cls = type(
        "ExampleTests", (base,), {"__module__": module, "test_it": lambda self: None}
    )
    return cls("test_it")


class LayerOfTests(SimpleTestCase):
    def test_layer_from_folder(self):
        self.assertEqual(layer_of("todos.tests.unit.test_models.A.test_a"), "unit")
        self.assertEqual(
            layer_of("todos.tests.integration.test_views.A.test_a"), "integration"
        )
        self.assertEqual(layer_of("todos.tests.cuj.test_journeys.A.test_a"), "cuj")

    def test_error_in_set_up_class_keeps_its_layer(self):
        self.assertEqual(
            layer_of("setUpClass (todos.tests.cuj.test_journeys.A)"), "cuj"
        )

    def test_test_outside_the_folders_has_no_layer(self):
        self.assertIsNone(layer_of("todos.tests.test_views.A.test_a"))
        self.assertIsNone(layer_of("todos.mytests.unit.test_a.A.test_a"))


class CheckLayersTests(SimpleTestCase):
    def test_tests_that_follow_the_rules_pass(self):
        check_layers(
            [
                make_test("todos.tests.unit.test_x"),
                make_test("todos.tests.integration.test_x", TestCase),
                make_test("todos.tests.cuj.test_x", StaticLiveServerTestCase),
            ]
        )

    def test_test_without_layer_is_refused(self):
        with self.assertRaisesMessage(
            TestLayerError, "not in a unit/, integration/ or cuj/"
        ):
            check_layers([make_test("todos.tests.test_x")])

    def test_unit_test_with_database_is_refused(self):
        with self.assertRaisesMessage(TestLayerError, "SimpleTestCase"):
            check_layers([make_test("todos.tests.unit.test_x", TestCase)])

    def test_cuj_test_without_live_server_is_refused(self):
        with self.assertRaisesMessage(TestLayerError, "StaticLiveServerTestCase"):
            check_layers([make_test("todos.tests.cuj.test_x", TestCase)])


class LayeredTestResultTests(SimpleTestCase):
    def test_results_are_counted_per_layer(self):
        result = LayeredTestResult(io.StringIO(), descriptions=False, verbosity=0)
        unit = make_test("todos.tests.unit.test_x")
        integration = make_test("todos.tests.integration.test_x")
        try:
            raise AssertionError("broken")
        except AssertionError as error:
            failure = (type(error), error, error.__traceback__)

        result.addSuccess(unit)
        result.addSuccess(unit)
        result.addFailure(integration, failure)
        result.addSkip(integration, "not today")

        self.assertEqual(result.layer_counts["unit"]["passed"], 2)
        self.assertEqual(result.layer_counts["integration"]["failed"], 1)
        self.assertEqual(result.layer_counts["integration"]["skipped"], 1)


class FormatSummaryTests(SimpleTestCase):
    def test_summary_counts_per_layer(self):
        summary = format_summary(
            {
                "cuj": {"passed": 1},
                "integration": {"passed": 9, "failed": 1},
                "unit": {"passed": 35, "errors": 2, "skipped": 1},
            }
        )
        self.assertEqual(
            summary,
            "Test layers\n"
            "  CUJ           1 passed\n"
            "  Integration   9 passed, 1 failed\n"
            "  Unit         35 passed, 2 errors, 1 skipped",
        )

    def test_layer_without_tests_says_so(self):
        self.assertIn(
            "  CUJ          no tests", format_summary({"unit": {"passed": 1}})
        )

    def test_tests_without_a_layer_get_their_own_line(self):
        summary = format_summary({None: {"errors": 1}})
        self.assertIn("  No layer      0 passed, 1 error", summary)
