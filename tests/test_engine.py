"""engine.py must route each request to the right provider and speech backend."""
import unittest
from unittest.mock import patch

from brain import BrainError
import engine


class ModelRoutingTests(unittest.TestCase):
    def test_claude_ids_use_the_subscription_adapter_and_need_no_key(self):
        for model in ("sonnet", "haiku", "opus", "claude-opus-5"):
            self.assertEqual(engine.provider(model), "claude")
            self.assertFalse(engine.needs_key(model))
            self.assertEqual(engine.label(model), "Claude")

    def test_gemini_ids_still_use_the_https_transport_and_need_a_key(self):
        self.assertEqual(engine.provider("gemini-3.8-flash"), "gemini")
        self.assertTrue(engine.needs_key("gemini-3.8-flash"))
        self.assertEqual(engine.label("gemini-3.8-flash"), "Gemini")

    def test_an_unknown_model_is_rejected_before_any_request_is_made(self):
        for model in ("", "gpt-4", "sonnet; del *", None, "claude-" + "x" * 200):
            self.assertFalse(engine.valid_model(model))
            with self.assertRaises(BrainError):
                engine.provider(model)

    def test_ask_dispatches_on_the_model_id(self):
        with (patch("engine.claude_brain.ask", return_value="claude") as claude,
              patch("engine.brain.ask", return_value="gemini") as gemini):
            self.assertEqual(engine.ask("", "sonnet", [], "hi"), "claude")
            self.assertEqual(engine.ask("k", "gemini-3.8-flash", [], "hi"), "gemini")
        claude.assert_called_once()
        gemini.assert_called_once()

    def test_ask_screen_dispatches_on_the_model_id(self):
        with (patch("engine.claude_brain.ask_screen", return_value="claude") as claude,
              patch("engine.brain.ask_screen", return_value="gemini") as gemini):
            self.assertEqual(engine.ask_screen("", "opus", "goal", [], b"png"), "claude")
            self.assertEqual(engine.ask_screen("k", "gemini-3.8-flash", "goal", [], b"png"), "gemini")
        claude.assert_called_once()
        gemini.assert_called_once()


class SpeechRoutingTests(unittest.TestCase):
    def test_installed_whisper_wins_over_the_cloud_even_in_gemini_mode(self):
        with (patch("engine.local_speech_installed", return_value=True),
              patch("engine.local_voice.transcribe", return_value="ok") as local,
              patch("engine.brain.transcribe") as cloud):
            self.assertEqual(engine.transcribe("k", "gemini-3.8-flash", b"wav"), "ok")
        local.assert_called_once()
        cloud.assert_not_called()

    def test_claude_mode_never_sends_audio_to_a_cloud_service(self):
        with (patch("engine.local_speech_installed", return_value=False),
              patch("engine.local_voice.diagnostic", return_value="not installed"),
              patch("engine.brain.transcribe") as stt,
              patch("engine.brain.synthesize") as tts):
            with self.assertRaises(BrainError):
                engine.transcribe("", "sonnet", b"wav")
            with self.assertRaises(BrainError):
                engine.speak("", "sonnet", "hello")
        stt.assert_not_called()
        tts.assert_not_called()

    def test_gemini_mode_still_speaks_through_the_cloud_without_whisper(self):
        with (patch("engine.local_speech_installed", return_value=False),
              patch("engine.brain.synthesize", return_value=b"") as tts,
              patch("engine.voice.play") as play):
            engine.speak("k", "gemini-3.8-flash", "hello")
        tts.assert_called_once()
        play.assert_called_once()

    def test_a_cancelled_local_transcription_reports_as_stopped(self):
        with (patch("engine.local_speech_installed", return_value=True),
              patch("engine.local_voice.transcribe",
                    side_effect=engine.local_voice.VoiceCancelled("cancelled"))):
            with self.assertRaises(BrainError) as caught:
                engine.transcribe("", "sonnet", b"wav")
        self.assertEqual(str(caught.exception), "Stopped")

    def test_a_local_voice_failure_surfaces_its_own_explanation(self):
        with (patch("engine.local_speech_installed", return_value=True),
              patch("engine.local_voice.transcribe",
                    side_effect=engine.local_voice.VoiceError("checksum mismatch"))):
            with self.assertRaises(BrainError) as caught:
                engine.transcribe("", "sonnet", b"wav")
        self.assertIn("checksum mismatch", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
