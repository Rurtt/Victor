"""The low-risk action tier runs without a click; everything else still asks."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from actions import AUTO_RUN, PolicyError, validate
from app import VictorApp
from brain import Reply
from local_store import LocalStore


class TierMembershipTests(unittest.TestCase):
    def test_only_bounded_reversible_actions_run_unattended(self):
        self.assertEqual(set(AUTO_RUN), {"media", "open_app", "open_folder", "search_web"})

    def test_actions_that_reach_people_or_take_control_always_ask(self):
        for name in ("discord_send", "control_screen", "open_website", "save_note"):
            self.assertNotIn(name, AUTO_RUN)

    def test_spotify_is_a_permitted_app_and_unknown_apps_are_not(self):
        validate({"name": "open_app", "arguments": {"app": "spotify"}})
        for app in ("cmd", "powershell", "spotify.exe", "../spotify"):
            with self.assertRaises(PolicyError):
                validate({"name": "open_app", "arguments": {"app": app}})


class AutoRunFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = VictorApp(store=LocalStore(Path(self.temp.name)))
        self.app.withdraw()
        self.app.key = "test-key"
        self.runner = Mock(return_value="Sent to Windows: skip track")
        self.app.gate.runner = self.runner

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def settle(self, predicate, seconds=3):
        deadline = time.monotonic() + seconds
        while not predicate() and time.monotonic() < deadline:
            self.app.update()
            time.sleep(0.01)

    def test_a_media_action_runs_with_no_pending_proposal(self):
        a = self.app
        action = {"name": "media", "arguments": {"command": "next_track"}}
        with patch("app.ask", return_value=Reply("\u0e15\u0e48\u0e2d\u0e44\u0e1b", [action])):
            a.input.insert("1.0", "next song")
            a.send()
            self.settle(lambda: self.runner.called)
        self.runner.assert_called_once()
        self.assertEqual(a.proposals, [])
        self.assertEqual(a.gate.pending, {})

    def test_screen_control_still_waits_for_a_click(self):
        a = self.app
        action = {"name": "control_screen", "arguments": {"goal": "\u0e17\u0e33\u0e07\u0e32\u0e19"}}
        with patch("app.ask", return_value=Reply("ok", [action])):
            a.input.insert("1.0", "do a thing")
            a.send()
            self.settle(lambda: bool(a.proposals))
        self.runner.assert_not_called()
        self.assertEqual(len(a.proposals), 1)

    def test_a_failing_auto_action_reports_instead_of_raising(self):
        a = self.app
        self.runner.side_effect = PolicyError("Spotify is not installed")
        action = {"name": "open_app", "arguments": {"app": "spotify"}}
        with patch("app.ask", return_value=Reply("ok", [action])):
            a.input.insert("1.0", "open spotify")
            a.send()
            self.settle(lambda: any(kind == "ERROR" for _row, _label, kind in a.bubbles))
        self.assertTrue(any(kind == "ERROR" for _row, _label, kind in a.bubbles))
        self.assertEqual(a.proposals, [])


if __name__ == "__main__":
    unittest.main()
