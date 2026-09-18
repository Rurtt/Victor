import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

import local_voice as voice


def wav(samples=b'\xe8\x03' * 1600, rate=16000, channels=1):
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(samples)
    return stream.getvalue()


class LocalVoiceTests(unittest.TestCase):
    def test_bad_audio_and_silence_never_launch_process(self):
        inputs = [b'', b'junk', wav(b''), wav(b'\0\0' * 1600), wav(rate=44100),
                  wav(channels=2), wav(b'\xe8\x03' * (16000 * 60 + 1)), wav()[:-10]]
        with patch.object(voice.subprocess, 'Popen') as launch:
            for data in inputs:
                with self.subTest(size=len(data)), self.assertRaises(voice.VoiceError):
                    voice.transcribe(data)
        launch.assert_not_called()

    def test_fixed_transcription_and_temp_cleanup(self):
        seen = []
        def run(args, **kwargs):
            seen.extend(args)
            Path(args[args.index('-of') + 1] + '.txt').write_text('เปิดเครื่องคิดเลข', encoding='utf-8')
            self.assertEqual(kwargs['cwd'], voice.CLI.parent)
            self.assertEqual(args[args.index('-l') + 1], 'th')
            self.assertLessEqual(int(args[args.index('-t') + 1]), 4)
            self.assertEqual(Path(args[args.index('-m') + 1]), voice.MODEL)
        with patch.object(voice, '_verify_runtime'), patch.object(voice, '_run', side_effect=run):
            self.assertEqual(voice.transcribe(wav()), 'เปิดเครื่องคิดเลข')
        self.assertFalse(Path(seen[seen.index('-f') + 1]).parent.exists())

    def test_cancelled_process_is_terminated_and_reaped(self):
        process = Mock()
        process.poll.return_value = None
        process.communicate.side_effect = subprocess.TimeoutExpired('test', 0.1)
        with patch.object(voice.subprocess, 'Popen', return_value=process), self.assertRaises(voice.VoiceCancelled):
            voice._run(['fixed.exe'], cancelled=Mock(side_effect=[False, False, True]), timeout=10)
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=2)

    def test_timeout_kills_child_that_ignores_terminate(self):
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('test', 2), None]
        with patch.object(voice.subprocess, 'Popen', return_value=process), patch.object(voice.time, 'monotonic', side_effect=[0, 11]):
            with self.assertRaises(voice.VoiceError):
                voice._run(['fixed.exe'], cancelled=lambda: False, timeout=10)
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)

    def test_speech_text_is_stdin_not_command_and_backend_env_removed(self):
        process = Mock(returncode=0)
        process.poll.return_value = 0
        text = 'ไทย $(calc); "quotes"'
        with patch.dict(voice.os.environ, {'GGML_BACKEND_PATH': 'evil'}), patch.object(voice.subprocess, 'Popen', return_value=process) as launch:
            voice.speak(text)
        args, kwargs = launch.call_args
        self.assertNotIn(text, args[0])
        self.assertFalse(kwargs['shell'])
        self.assertNotIn('GGML_BACKEND_PATH', kwargs['env'])
        process.communicate.assert_called_once_with(input=text.encode('utf-8'), timeout=0.1)

    def test_manifest_requires_model_and_rechecks_changes_and_dropped_dll(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cli = root / 'runtime/whisper/whisper-cli.exe'
            model = root / 'models/ggml-small.bin'
            manifest = root / 'runtime/voice-manifest.json'
            cli.parent.mkdir(parents=True)
            model.parent.mkdir()
            cli.write_bytes(b'exe')
            model.write_bytes(b'model')
            files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in (cli, model)}
            with patch.multiple(voice, ROOT=root, CLI=cli, MODEL=model, MANIFEST=manifest):
                self.assertFalse(voice.ready())
                manifest.write_text(json.dumps({'files': files}), encoding='utf-8')
                self.assertTrue(voice.ready())
                (cli.parent / 'ggml-evil.dll').write_bytes(b'evil')
                self.assertFalse(voice.ready())
                (cli.parent / 'ggml-evil.dll').unlink()
                model.write_bytes(b'modified model')
                self.assertFalse(voice.ready())

    def test_wake_stop_reaps_and_is_idempotent(self):
        listener = voice.WakeListener(Mock())
        process = Mock()
        process.poll.return_value = None
        listener._process = process
        listener.stop()
        listener.stop()
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=2)


if __name__ == '__main__':
    unittest.main()
