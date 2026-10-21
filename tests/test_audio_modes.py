"""The three audio choices, end to end through compile → voice → mix → render command → QA.

Provider calls are mocked (no paid API is ever called by the test suite). Real ffmpeg is
used for the synthesised effects, the mix and the QA measurements.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import Env, ffmpeg, has_ffmpeg  # noqa: E402

from promo_engine import audio, qa, render, sfx_synth, sound, timeline, voiceover
from promo_engine.cli import main
from promo_engine.util import PromoError, read_json, redact

FAKE_KEY = "sk-test-0123456789abcdefSECRET"


def set_audio(env: Env, mode: str, provider: str | None = None) -> None:
    args = ["-w", str(env.ws.root), "init", "--product", str(env.product), "--audio", mode]
    if provider:
        args += ["--provider", provider]
    assert main(args) == 0


def fake_engine(calls: list):
    """Stands in for a TTS provider: a real 0.6 s tone, and the script as its transcript."""
    def engine(text, voice, direction, dest):
        calls.append(text)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=0.6",
                        "-ar", "48000", "-ac", "2", dest], check=True)
        return text
    return engine


def never_called(*_a, **_k):
    raise AssertionError("a voice engine was called although the audio mode has no voice-over")


@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class SynthesisedEffects(unittest.TestCase):
    def setUp(self):
        self.env = Env()

    def tearDown(self):
        self.env.close()

    def test_every_cue_name_has_a_short_audible_licence_clean_effect(self):
        lib = sfx_synth.build_library(self.env.tmp / "sfx")
        self.assertEqual(set(lib), set(sound.LIBRARY))
        for name, path in lib.items():
            secs = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                         "csv=p=0", str(path)], capture_output=True, text=True).stdout)
            self.assertLessEqual(secs, sound.MAX_EFFECT_SECONDS, name)
            peak = qa.max_volume(path)
            self.assertGreater(peak, -30, f"{name} is effectively silent")
        self.assertFalse(list((Path(sound.__file__).parents[2] / "renderer" / "public").glob("sfx/*.mp3")),
                         "no third-party effect files are bundled")

    def test_synthesis_is_deterministic(self):
        a = sfx_synth.build_library(self.env.tmp / "a")
        b = sfx_synth.build_library(self.env.tmp / "b")
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
        self.assertEqual({n: digest(p) for n, p in a.items()}, {n: digest(p) for n, p in b.items()})


@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class AudioModes(unittest.TestCase):
    def setUp(self):
        self.env = Env().with_artifacts()

    def tearDown(self):
        self.env.close()

    def _compile(self, mode, provider=None):
        set_audio(self.env, mode, provider)
        rc, rep = timeline.compile_timeline(self.env.ws)
        self.assertTrue(rep.ok, rep.summary())
        return rc

    def test_compile_carries_the_policy(self):
        vo = self._compile("voiceover", "files")
        self.assertEqual(vo["audioPolicy"], {"mode": "voiceover", "voiceover": True, "soundEffects": True, "music": False})
        self.assertGreaterEqual(len(vo["narration"]["lines"]), 3)
        self.assertTrue(vo["sound"]["cues"])
        fx = self._compile("effects")
        self.assertEqual((fx["narration"]["enabled"], fx["narration"]["lines"]), (False, []))
        self.assertIn("no voice-over", fx["narration"]["reason"])
        self.assertTrue(fx["sound"]["cues"])
        silent = self._compile("silent")
        self.assertEqual((silent["narration"]["lines"], silent["sound"]["cues"]), ([], []))
        self.assertIn("without an audio stream", self.env.ws.storyboard.read_text())
        for rc in (vo, fx, silent):
            self.assertNotIn("music", json.dumps(rc["sound"]).lower())
            self.assertIs(rc["audioPolicy"]["music"], False)

    def test_effects_and_silent_never_call_a_voice_engine(self):
        for mode in ("effects", "silent"):
            rc = self._compile(mode)
            with mock.patch.dict(voiceover.ENGINES, {k: never_called for k in voiceover.ENGINES}), \
                    mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": FAKE_KEY}), \
                    mock.patch.object(voiceover, "run", side_effect=AssertionError("network call")):
                m = voiceover.render_voice(self.env.ws, rc, self.env.ws.config())
            self.assertEqual((m["engine"], m["lines"]), ("none", []))

    def test_voiceover_plus_effects_mix(self):
        rc = self._compile("voiceover", "say")
        calls = []
        with mock.patch.dict(voiceover.ENGINES, {"say": fake_engine(calls)}), \
                mock.patch("shutil.which", side_effect=lambda b: f"/usr/bin/{b}"):
            vo = voiceover.render_voice(self.env.ws, rc, self.env.ws.config())
        self.assertEqual(calls, [n["text"] for n in rc["narration"]["lines"]])
        self.assertEqual(len(vo["lines"]), len(rc["narration"]["lines"]))
        m = audio.build_master(self.env.ws, rc)
        kinds = {s["kind"] for s in m["sources"]}
        self.assertEqual(kinds, {"sfx", "voice"})
        self.assertEqual(m["policy"]["mode"], "voiceover")
        self.assertTrue(qa.check_no_music(m, self.env.ws.master_audio, rc).ok)
        # Cues land at their scheduled times: the master is loud where the first cue is.
        first = m["sources"][0]
        self.assertTrue(qa.check_narration(json.loads((self.env.ws.vo_dir / "manifest.json").read_text()), rc).ok)
        self.assertGreaterEqual(first["at"], 0)

    def test_effects_only_mix_has_no_speech_even_with_stale_voice_files(self):
        rc_vo = self._compile("voiceover", "say")
        with mock.patch.dict(voiceover.ENGINES, {"say": fake_engine([])}), \
                mock.patch("shutil.which", side_effect=lambda b: f"/usr/bin/{b}"):
            voiceover.render_voice(self.env.ws, rc_vo, self.env.ws.config())
        rc = self._compile("effects")
        # The voice step for effects mode clears the takes; even if one were left, the mix ignores it.
        stale = json.loads((self.env.ws.vo_dir / "manifest.json").read_text())
        m = audio.build_master(self.env.ws, rc)
        self.assertEqual({s["kind"] for s in m["sources"]}, {"sfx"})
        self.assertTrue(stale["lines"], "precondition: voice takes existed on disk")
        rep = qa.check_no_music(m, self.env.ws.master_audio, rc)
        self.assertTrue(rep.ok, rep.summary())
        # A voice source smuggled into an effects-only mix is an error, and so is the sound of it.
        bad = dict(m, sources=m["sources"] + [{"kind": "voice", "source": "audio/vo/00.wav", "at": 1, "seconds": 1}])
        self.assertIn("speech", qa.check_no_music(bad, self.env.ws.master_audio, rc).summary())
        speechy = self.env.tmp / "speechy.wav"
        ffmpeg("-i", str(self.env.ws.master_audio), "-f", "lavfi", "-i", "sine=f=180:d=2,adelay=20000|20000",
               "-filter_complex", "[0][1]amix=inputs=2:normalize=0", str(speechy))
        self.assertIn("or speech", qa.check_no_music(m, speechy, rc).summary())

    def test_silent_mode_builds_nothing_and_removes_a_stale_master(self):
        rc_fx = self._compile("effects")
        audio.build_master(self.env.ws, rc_fx)
        self.assertTrue(self.env.ws.master_audio.exists())
        rc = self._compile("silent")
        m = audio.build_master(self.env.ws, rc)
        self.assertEqual((m["master"], m["sources"]), (None, []))
        self.assertFalse(self.env.ws.master_audio.exists(), "a stale master could be attached")
        self.assertTrue(qa.check_no_music(m, self.env.ws.master_audio, rc).ok)

    def test_silent_render_is_muted_and_attaches_no_audio(self):
        rc = self._compile("silent")
        audio.build_master(self.env.ws, rc)
        cmds = self._fake_render()
        self.assertIn("--muted", cmds[0])
        props = read_json(self.env.ws.root / "build" / "render-props.json")
        self.assertIsNone(props["audio"]["src"])

    def test_sound_modes_refuse_to_render_without_a_master(self):
        self._compile("effects")
        with self.assertRaises(PromoError) as cm, mock.patch.object(render, "free_gb", return_value=50.0):
            self._fake_render()
        self.assertIn("no audio master", str(cm.exception))
        rc = read_json(self.env.ws.render_config)
        audio.build_master(self.env.ws, rc)
        cmds = self._fake_render()
        self.assertNotIn("--muted", cmds[0])
        self.assertEqual(read_json(self.env.ws.root / "build" / "render-props.json")["audio"]["src"], "audio/master.wav")

    def _fake_render(self) -> list[list[str]]:
        cmds = []

        def fake_run(cmd, **kw):
            cmds.append(cmd)
            Path(cmd[5]).parent.mkdir(parents=True, exist_ok=True)
            Path(cmd[5]).write_bytes(b"x")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch.object(render, "ensure_renderer"), mock.patch.object(render.subprocess, "run", fake_run), \
                mock.patch.object(render, "free_gb", return_value=50.0):  # independent of this machine's disk
            render.render(self.env.ws, "16:9")
        return cmds


@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class SilentExportQA(unittest.TestCase):
    def setUp(self):
        self.env = Env().with_artifacts()
        set_audio(self.env, "silent")
        self.rc, _ = timeline.compile_timeline(self.env.ws)
        self.rc.update(duration=3.0, durationInFrames=90)

    def tearDown(self):
        self.env.close()

    def _video(self, audio_args: list[str]) -> Path:
        out = self.env.tmp / f"v{len(list(self.env.tmp.glob('v*.mp4')))}.mp4"
        ffmpeg("-f", "lavfi", "-i", "testsrc2=s=320x180:d=3:r=30", *audio_args, "-pix_fmt", "yuv420p",
               "-c:v", "libx264", "-preset", "ultrafast", str(out))
        return out

    def test_no_audio_stream_passes(self):
        rep, facts = qa.check_video(self._video([]), "16:9", self.rc, scale=320 / 1920)
        self.assertNotIn("audio", rep.summary())
        self.assertIsNone(facts["audio"])

    def test_a_silent_stream_is_accepted_only_after_verification(self):
        v = self._video(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d=3", "-c:a", "aac", "-shortest"])
        rep, _ = qa.check_video(v, "16:9", self.rc, scale=320 / 1920)
        self.assertEqual([i.level for i in rep.issues if "audio" in i.message], ["warning"])
        loud = self._video(["-f", "lavfi", "-i", "sine=f=440:d=3", "-c:a", "aac", "-shortest"])
        rep, _ = qa.check_video(loud, "16:9", self.rc, scale=320 / 1920)
        self.assertIn("audible audio stream", rep.summary())


class Providers(unittest.TestCase):
    """OpenRouter and OpenAI request handling, with the network mocked."""

    def setUp(self):
        self.env = Env().with_artifacts()

    def tearDown(self):
        self.env.close()

    def test_auto_never_falls_back_to_a_local_voice(self):
        set_audio(self.env, "voiceover")
        rc, _ = timeline.compile_timeline(self.env.ws)
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "OPENAI_API_KEY": ""}), \
                mock.patch.dict(voiceover.ENGINES, {k: never_called for k in voiceover.ENGINES}):
            with self.assertRaises(PromoError) as cm:
                voiceover.render_voice(self.env.ws, rc, self.env.ws.config())
        self.assertIn("not resolved", str(cm.exception))

    def test_openai_take_is_verified_by_transcription_and_key_stays_off_argv(self):
        seen: list[tuple[list[str], bytes | None]] = []
        heard = iter(["Sure! Here is a great line for you.", "Drop the receipts in."])

        def fake_run(cmd, **kw):
            seen.append((cmd, kw.get("input")))
            if cmd[0] == "curl" and voiceover.OA_SPEECH in cmd:
                out = cmd[cmd.index("-o") + 1]
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=0.5", out], check=True)
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            if cmd[0] == "curl" and voiceover.OA_TRANSCRIBE in cmd:
                return subprocess.CompletedProcess(cmd, 0, json.dumps({"text": next(heard)}).encode(), b"")
            return subprocess.run(cmd, capture_output=True, **kw)

        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": FAKE_KEY}), mock.patch.object(voiceover, "run", fake_run):
            path = voiceover.take("openai", "Drop the receipts in.", "coral", "calm", str(self.env.tmp / "cache"))
        self.assertTrue(Path(path).is_file())
        speech = [c for c, _ in seen if voiceover.OA_SPEECH in c]
        self.assertEqual(len(speech), 2, "the first take answered instead of reading, so it was retried")
        for cmd, stdin in seen:
            self.assertFalse(any(FAKE_KEY in a for a in cmd), "key on the command line")
            if cmd[0] == "curl":
                self.assertIn(FAKE_KEY.encode(), stdin)
        body = json.loads(speech[0][speech[0].index("--data-binary") + 1])
        self.assertEqual((body["model"], body["input"], body["response_format"]), ("gpt-4o-mini-tts", "Drop the receipts in.", "wav"))

    def test_a_take_that_never_reads_the_script_fails_after_bounded_retries(self):
        n = []

        def answering(text, voice, direction, dest):
            n.append(1)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=0.4", dest], check=True)
            return "I'm sorry, I can't assist with that."

        with mock.patch.dict(voiceover.ENGINES, {"openrouter": answering}):
            with self.assertRaises(PromoError) as cm:
                voiceover.take("openrouter", "Scan any label.", "cedar", "calm", str(self.env.tmp / "c"), attempts=3)
        self.assertEqual(len(n), 3)
        self.assertIn("Could not get a clean read", str(cm.exception))
        self.assertFalse(list((self.env.tmp / "c").glob("*.wav")), "a failed take is not cached")

    def test_openrouter_model_must_produce_audio(self):
        listing = {"data": [{"id": "openai/gpt-audio", "architecture": {"output_modalities": ["text"]}}]}
        with mock.patch.object(voiceover, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(listing), "")):
            with self.assertRaises(PromoError) as cm:
                voiceover.check_openrouter_model()
        self.assertIn("does not produce audio", str(cm.exception))
        listing["data"][0]["architecture"]["output_modalities"] = ["text", "audio"]
        with mock.patch.object(voiceover, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(listing), "")):
            voiceover.check_openrouter_model()

    def test_api_errors_are_safe_and_actionable(self):
        def failing(cmd, **kw):
            raise PromoError(f"curl failed (exit 22):\n  401 Unauthorized for key {FAKE_KEY}")

        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": FAKE_KEY}), mock.patch.object(voiceover, "run", failing):
            with self.assertRaises(PromoError) as cm:
                voiceover.tts_openai("Hi there.", "coral", "calm", str(self.env.tmp / "x.wav"))
            rendered = cm.exception.render()
        self.assertIn("401 Unauthorized", rendered)  # the cause stays visible
        self.assertNotIn(FAKE_KEY, rendered)
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": FAKE_KEY}):
            self.assertEqual(redact(f"key={FAKE_KEY}"), "key=<OPENAI_API_KEY>")

    def test_cache_key_covers_every_generation_input(self):
        base = ("openrouter", "Drop the receipts in.", "cedar", "calm")
        k = voiceover.cache_key(*base)
        self.assertEqual(k, voiceover.cache_key(*base), "stable")
        for i, changed in enumerate(("openai", "Drop them in.", "sage", "excited")):
            args = list(base)
            args[i] = changed
            self.assertNotEqual(k, voiceover.cache_key(*args), f"input {i} must change the key")
        with mock.patch.object(voiceover, "PIPELINE", voiceover.PIPELINE + 1):
            self.assertNotEqual(k, voiceover.cache_key(*base))
        with mock.patch.dict(voiceover.MODELS, {"openrouter": "openai/gpt-audio-mini"}):
            self.assertNotEqual(k, voiceover.cache_key(*base))

    @unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
    def test_no_secret_reaches_the_workspace(self):
        set_audio(self.env, "voiceover", "say")
        rc, _ = timeline.compile_timeline(self.env.ws)
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": FAKE_KEY, "OPENAI_API_KEY": FAKE_KEY + "2"}), \
                mock.patch.dict(voiceover.ENGINES, {"say": fake_engine([])}), \
                mock.patch("shutil.which", side_effect=lambda b: f"/usr/bin/{b}"):
            voiceover.render_voice(self.env.ws, rc, self.env.ws.config())
            audio.build_master(self.env.ws, rc)
        for p in self.env.ws.root.rglob("*"):
            if p.is_file() and p.suffix in (".json", ".md", ".txt", ".log", ""):
                self.assertNotIn(FAKE_KEY, p.read_text(errors="ignore"), p)


if __name__ == "__main__":
    unittest.main()
