import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from routes import best_route
from analysis import demo_index
from database import init_db, add_report, fetch

class CoreTests(unittest.TestCase):
    def test_routes_change_when_safety_weight_changes(self):
        shortest, dist1, _ = best_route(safety_weight=0)
        safer, dist2, _ = best_route(safety_weight=4)
        self.assertEqual(shortest, ["المدرسة", "الميدان", "المستشفى"])
        self.assertEqual(safer, ["المدرسة", "الحديقة", "المستشفى"])
        self.assertGreater(dist2, dist1)
    def test_demo_indicator_bounds(self):
        self.assertEqual(demo_index(0, 0), 0)
        self.assertLessEqual(demo_index(300, 50), 70)
    def test_db_insert(self):
        import database
        from tempfile import TemporaryDirectory
        old = database.DB_PATH
        with TemporaryDirectory() as tmp:
            database.DB_PATH = Path(tmp) / "test.sqlite3"
            try:
                init_db()
                add_report("حفرة", "متوسطة", "Test", 30.0, 31.0)
                self.assertEqual(len(fetch("reports")), 1)
                with self.assertRaises(ValueError):
                    fetch("not_a_table")
            finally:
                database.DB_PATH = old

if __name__ == "__main__":
    unittest.main()
