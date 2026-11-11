"""
Checks that a signed-in user sees and changes only the sensors they own, while an
admin manages every sensor. Needs a throwaway Postgres database in TEST_DATABASE_URL.
"""
import os
import unittest

from tests.shared_app import get_server

TEST_DB = os.environ.get("TEST_DATABASE_URL")
if TEST_DB:
    os.environ["DATABASE_URL"] = TEST_DB
    os.environ.setdefault("SECRET_KEY", "test")


@unittest.skipUnless(TEST_DB, "TEST_DATABASE_URL not set")
class Ownership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = get_server()

    def setUp(self):
        from server.database import db, run_migrations
        from server.models import User, create_or_update_sensor
        self.ctx = self.server.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        run_migrations()

        self.users = {}
        for name, is_admin in (("admin", True), ("alice", False), ("bob", False)):
            user = User(username=name, is_admin=is_admin)
            user.set_password("right")
            db.session.add(user)
            db.session.commit()
            self.users[name] = user.id

        create_or_update_sensor("alice_sonde", 30.5, -87.9, "sonde", user_id=self.users["alice"])
        create_or_update_sensor("alice_bench", None, None, "sonde", user_id=self.users["alice"], testing=True)
        create_or_update_sensor("bob_sonde", 30.6, -87.8, "sonde", user_id=self.users["bob"])
        # From before ownership was recorded, so nobody owns it
        create_or_update_sensor("old_sonde", 30.7, -87.7, "sonde")
        from server.models import user_sensor_association, get_sensor_by_name
        db.session.execute(user_sensor_association.delete().where(
            user_sensor_association.c.sensor_id == get_sensor_by_name("old_sonde").id))
        db.session.commit()

    def tearDown(self):
        from server.database import db
        db.session.remove()
        self.ctx.pop()

    def as_user(self, name):
        from flask import session
        context = self.server.test_request_context()
        context.push()
        self.addCleanup(context.pop)
        session.update(user_logged_in=True, user_id=self.users[name])

    def names(self, testing=None):
        from dash_app.access import managed_sensors
        return sorted(s["name"] for s in managed_sensors(testing=testing))

    def test_a_user_sees_only_their_own_sensors(self):
        self.as_user("alice")
        self.assertEqual(self.names(), ["alice_bench", "alice_sonde"])
        self.assertEqual(self.names(testing=True), ["alice_bench"])

    def test_an_admin_sees_every_sensor_even_unowned_ones(self):
        self.as_user("admin")
        self.assertEqual(self.names(), ["alice_bench", "alice_sonde", "bob_sonde", "old_sonde"])

    def test_signed_out_sees_nothing(self):
        from flask import session
        from dash_app.access import managed_sensor
        self.as_user("alice")
        session["user_logged_in"] = False
        self.assertEqual(self.names(), [])
        self.assertIsNone(managed_sensor("alice_sonde"))

    def test_a_user_cannot_delete_someone_elses_sensor(self):
        from dash_app.callbacks.update_sensor import delete_error
        from server.models import get_sensor_by_name
        self.as_user("bob")
        self.assertEqual(delete_error("alice_sonde", "right"), "Could not find sensor 'alice_sonde'.")
        self.assertIsNotNone(get_sensor_by_name("alice_sonde"))
        self.assertIsNone(delete_error("bob_sonde", "right"))
        self.assertIsNone(get_sensor_by_name("bob_sonde"))

    def test_only_the_owner_or_an_admin_can_see_a_test_device(self):
        from dash_app.callbacks.dashboard import can_view
        self.as_user("bob")
        self.assertFalse(can_view("alice_bench"))
        self.assertTrue(can_view("alice_sonde"))  # Live sensors are public
        self.as_user("alice")
        self.assertTrue(can_view("alice_bench"))
        self.as_user("admin")
        self.assertTrue(can_view("alice_bench"))

    def test_a_new_sensor_belongs_to_its_creator_and_the_admins(self):
        from server.models import get_sensor_by_name
        owners = sorted(u.username for u in get_sensor_by_name("alice_sonde").users)
        self.assertEqual(owners, ["admin", "alice"])


if __name__ == "__main__":
    unittest.main()
