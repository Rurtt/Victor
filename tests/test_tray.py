"""The Windows tray guard and message loop, exercised without the rest of the app."""
import time
import unittest

import tray


class InstanceGuardTests(unittest.TestCase):
    def tearDown(self):
        tray.release_instance()

    def test_the_guard_is_reentrant_within_one_process_and_releasable(self):
        self.assertTrue(tray.acquire_instance())
        self.assertTrue(tray.acquire_instance())
        tray.release_instance()
        self.assertTrue(tray.acquire_instance())


class TrayIconTests(unittest.TestCase):
    def wait_until_stopped(self, icon):
        deadline = time.monotonic() + 3
        while icon.running and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(icon.running)

    def test_it_starts_stops_and_reports_menu_events(self):
        seen = []
        icon = tray.Tray(None, seen.append)
        self.assertTrue(icon.start())
        try:
            self.assertTrue(icon.running)
            icon.set_wake(True)
            icon._emit("open")
        finally:
            icon.stop()
        self.wait_until_stopped(icon)
        self.assertEqual(seen, ["open"])

    def test_a_failing_callback_cannot_take_down_the_message_thread(self):
        def explode(event):
            raise ValueError("callback bug")

        icon = tray.Tray(None, explode)
        self.assertTrue(icon.start())
        try:
            icon._emit("open")
            self.assertTrue(icon.running)
        finally:
            icon.stop()
        self.wait_until_stopped(icon)

    def test_stop_is_safe_before_start_and_when_repeated(self):
        icon = tray.Tray(None, lambda event: None)
        icon.stop()
        icon.stop()
        self.assertFalse(icon.running)


if __name__ == "__main__":
    unittest.main()
