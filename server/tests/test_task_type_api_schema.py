import unittest

from app.api.task_types import TaskTypeOut


class TaskTypeOutTest(unittest.TestCase):
    def test_null_predecessors_from_legacy_rows_are_returned_as_empty_list(self):
        value = TaskTypeOut.model_validate({
            "id": 1,
            "name": "溶液配制",
            "code": "solution_preparation",
            "resource_type": "human",
            "description": None,
            "is_active": True,
            "sort_order": 0,
            "predecessor_type_ids": None,
        })

        self.assertEqual([], value.predecessor_type_ids)


if __name__ == "__main__":
    unittest.main()
