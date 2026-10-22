import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import auth, storage


class EnsureUsersTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.patches = [
            patch("backend.auth.DATA_DIR", self.tmp),
            patch("backend.storage.DATA_DIR", self.tmp),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_first_start_creates_department_d(self):
        auth.ensure_users()
        user = auth.find_user("d")
        self.assertIsNotNone(user)
        self.assertEqual(user["department"], "事业部D")
        self.assertEqual(user["role"], "user")
        self.assertEqual(user["module"], "outreach")
        self.assertTrue(auth.verify_password("BuD@knx2026", user["password_hash"]))

    def test_existing_file_gets_missing_department_without_resetting_password(self):
        old_hash = auth.hash_password("KeepA@old")
        storage.write_collection(
            auth.USERS_FILE,
            [
                {
                    "username": "a",
                    "password_hash": old_hash,
                    "display_name": "事业部A",
                    "department": "事业部A",
                    "role": "user",
                    "module": "outreach",
                }
            ],
        )
        auth.ensure_users()
        kept = auth.find_user("a")
        self.assertEqual(kept["password_hash"], old_hash)
        self.assertTrue(auth.verify_password("KeepA@old", kept["password_hash"]))
        self.assertFalse(auth.verify_password("BuA@knx2026", kept["password_hash"]))
        newbie = auth.find_user("d")
        self.assertIsNotNone(newbie)
        self.assertTrue(auth.verify_password("BuD@knx2026", newbie["password_hash"]))

    def test_second_run_does_not_duplicate(self):
        auth.ensure_users()
        first = [user["username"] for user in auth.list_users()]
        auth.ensure_users()
        second = [user["username"] for user in auth.list_users()]
        self.assertEqual(first, second)
        self.assertEqual(len(first), len(set(first)))
        self.assertIn("d", first)
        self.assertIn("stock-a", first)


if __name__ == "__main__":
    unittest.main()
