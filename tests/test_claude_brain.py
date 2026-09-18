import json
import unittest
from unittest.mock import patch

import claude_brain as c
from brain import BrainError


class ClaudeTests(unittest.TestCase):
    def test_no_api_environment_fallback(self):
        with patch.dict(c.os.environ, {"ANTHROPIC_API_KEY": "secret", "ANTHROPIC_BASE_URL": "bad",
                                      "CLAUDE_CODE_USE_BEDROCK": "1"}):
            env = c.subscription_environment()
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("ANTHROPIC_BASE_URL", env)
        self.assertNotIn("CLAUDE_CODE_USE_BEDROCK", env)

    def test_structured_output_and_errors(self):
        raw = json.dumps({"type": "result", "subtype": "success", "structured_output": {"reply": "สวัสดี", "actions": []}}).encode()
        self.assertEqual(c._data(raw)["reply"], "สวัสดี")
        for bad in (b'{}', b'[]', b'not json', b'{"type":"result","is_error":true}'):
            with self.assertRaises(BrainError):
                c._data(bad)

    def test_summary_rejects_actions_and_excludes_history(self):
        action = {"name": "open_app", "arguments": {"app": "calculator"}}
        with patch.object(c, "_request", return_value={"reply": "summary", "actions": [action]}) as run:
            with self.assertRaises(BrainError):
                c.ask("", "sonnet", [{"role": "user", "text": "private history"}], "document", summary=True)
        self.assertNotIn("private history", run.call_args.args[3][0]["text"])

    def test_transport_disables_tools_and_preserves_thai(self):
        raw = b'{"type":"result","subtype":"success","structured_output":{"reply":"ok","actions":[]}}'
        with patch.object(c, "check_login"), patch.object(c, "_run", return_value=raw) as run:
            self.assertEqual(c.ask("", "sonnet", [], "สวัสดี").text, "ok")
        args, payload = run.call_args.args
        self.assertIn("--safe-mode", args)
        self.assertEqual(args[args.index("--tools") + 1], "")
        self.assertEqual(args[args.index("--mcp-config") + 1], '{"mcpServers":{}}')
        self.assertIn("สวัสดี", payload.decode())

    def test_model_is_not_command_input(self):
        with self.assertRaises(BrainError), patch.object(c, "_run") as run:
            c.ask("", "sonnet & calc", [], "hello")
        run.assert_not_called()

    def test_cancel_before_spawn(self):
        with patch.object(c.subprocess, "Popen") as popen:
            with self.assertRaises(BrainError):
                c._run([], cancelled=lambda: True)
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
