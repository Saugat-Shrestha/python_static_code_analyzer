"""Run PyScan over its own source code and require a clean result.

This started as a manual sanity check and immediately paid for itself: it found
a false positive on `__init__.py` re-exports, one genuinely dead import, and a
`main` function that was over the complexity limit the tool itself enforces.

Keeping it as a test means the analyser now holds its own code to the same
standard it holds everyone else's, and it cannot quietly drift back over the
line.
"""

import glob
import os
import unittest

from pyscan.analyzer import analyze_file

PACKAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pyscan")


def package_files():
    return sorted(glob.glob(os.path.join(PACKAGE_DIR, "*.py")))


class TestPyScanAnalysesItself(unittest.TestCase):

    def test_the_package_has_source_files_to_check(self):
        # Guards against the test silently passing because the glob found nothing.
        self.assertGreater(len(package_files()), 5)

    def test_every_module_is_free_of_issues(self):
        for path in package_files():
            with self.subTest(module=os.path.basename(path)):
                report = analyze_file(path)
                described = [
                    "%d:%s %s" % (issue.line, issue.rule_id, issue.message)
                    for issue in report.issues
                ]
                self.assertEqual(described, [], "\n".join(described))

    def test_no_module_exceeds_the_default_complexity_limit(self):
        for path in package_files():
            with self.subTest(module=os.path.basename(path)):
                metrics = analyze_file(path).metrics
                self.assertLessEqual(metrics.max_complexity, 10)


if __name__ == "__main__":
    unittest.main()
