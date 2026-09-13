import unittest

from kapisch_validation.presentations import render_metrics, render_state_markdown


class PresentationTests(unittest.TestCase):
    def test_state_markdown_regenerates_from_semantic_state(self) -> None:
        left = {
            "task_id": "é",
            "completed_node_ids": ["T02", "T01"],
            "workflow_status": "running",
        }
        right = dict(reversed(list(left.items())))
        right["completed_node_ids"] = ["T01", "T02"]
        expected = (
            '# KAPISCH State\n\n```json\n'
            '{"completed_node_ids":["T01","T02"],"task_id":"é","workflow_status":"running"}\n'
            '```\n'
        ).encode("utf-8")
        self.assertEqual(render_state_markdown(left), expected)
        self.assertEqual(render_state_markdown(left), render_state_markdown(right))

    def test_state_membership_duplicates_and_malformed_values_fail(self) -> None:
        with self.assertRaises(ValueError):
            render_state_markdown({"completed_node_ids": ["T01", "T01"]})
        with self.assertRaises(ValueError):
            render_state_markdown({"failed_node_ids": ["T01", 2]})

    def test_metrics_sort_stable_records_without_changing_observations(self) -> None:
        records = [
            {"terminal_id": "AT-T02-1", "elapsed_ms": "unavailable", "role": "reviewer"},
            {"terminal_id": "AT-T01-1", "elapsed_ms": 12, "role": "implementer"},
        ]
        first = render_metrics(records, {"terminal_count": 2})
        second = render_metrics(list(reversed(records)), {"terminal_count": 2})
        self.assertEqual(first, second)
        self.assertIn(b'"elapsed_ms":"unavailable"', first)
        changed = [dict(records[0]), dict(records[1], elapsed_ms=13)]
        self.assertNotEqual(first, render_metrics(changed, {"terminal_count": 2}))

    def test_metrics_require_unique_non_empty_terminal_ids(self) -> None:
        with self.assertRaises(ValueError):
            render_metrics([{"terminal_id": ""}], {})
        with self.assertRaises(ValueError):
            render_metrics([{"terminal_id": "AT-1"}, {"terminal_id": "AT-1"}], {})


if __name__ == "__main__":
    unittest.main()
