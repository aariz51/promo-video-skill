"""Mode selection, the run configuration, the opening questions and voice-provider choice."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402
from helpers import Env, fake_watch_script, ffmpeg, has_ffmpeg  # noqa: E402

from promo_engine import analyzer, config, providers, questions, reference_input, watcher
from promo_engine.cli import main
from promo_engine.util import PromoError, write_json

NO_KEYS = {"PATH": os.environ.get("PATH", "")}


def ids(ws, env=NO_KEYS) -> list[str]:
    return [q["id"] for q in questions.plan(ws, env)]


class ModeSelection(unittest.TestCase):
    def setUp(self):
        self.env = Env()

    def tearDown(self):
        self.env.close()

    def test_no_reference_selects_autonomous_mode(self):
        for answer in (None, "", "none", "No", "skip"):
            self.assertEqual(reference_input.resolve(answer).mode, "autonomous", repr(answer))

    def test_a_youtube_url_selects_reference_mode(self):
        ref = reference_input.resolve("youtu.be/dQw4w9WgXcQ")
        self.assertEqual((ref.kind, ref.mode), ("youtube", "reference"))
        self.assertEqual(ref.source, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_another_video_url_selects_reference_mode(self):
        ref = reference_input.resolve("https://vimeo.com/76979871")
        self.assertEqual((ref.kind, ref.mode), ("url", "reference"))

    @unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
    def test_a_local_video_selects_reference_mode(self):
        clip = self.env.tmp / "ref clip.mp4"
        ffmpeg("-f", "lavfi", "-i", "color=c=red:s=160x90:d=1:r=25", "-pix_fmt", "yuv420p", str(clip))
        ref = reference_input.resolve(str(clip))
        self.assertEqual((ref.kind, ref.mode, ref.source), ("file", "reference", str(clip.resolve())))
        rel = reference_input.resolve("ref clip.mp4", base=self.env.tmp)
        self.assertEqual(rel.source, str(clip.resolve()))

    @unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
    def test_unusable_local_files_are_rejected_with_a_reason(self):
        fake = self.env.tmp / "notes.mp4"
        fake.write_text("this is not a video")
        clip = self.env.tmp / "good.mp4"
        ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=160x90:d=2:r=25", "-pix_fmt", "yuv420p", str(clip))
        cut = self.env.tmp / "truncated.mp4"
        cut.write_bytes(clip.read_bytes()[:400])
        audio_only = self.env.tmp / "voice.mp4"
        ffmpeg("-f", "lavfi", "-i", "sine=f=440:d=1", str(audio_only))
        cases = {str(fake): "cannot be decoded", str(cut): "cannot be decoded",
                 str(audio_only): "no video stream", str(self.env.tmp / "missing.mp4"): "not found",
                 str(self.env.product / "README.md"): "unsupported reference file type"}
        for raw, why in cases.items():
            with self.assertRaises(PromoError, msg=raw) as cm:
                reference_input.resolve(raw)
            self.assertIn(why, str(cm.exception), raw)

    def test_non_urls_are_never_guessed(self):
        for raw in ("ftp://example.com/v.mp4", "just some words", "https://www.youtube.com/@chan"):
            with self.assertRaises(PromoError, msg=raw):
                reference_input.resolve(raw)

    def test_init_records_the_mode_and_never_asks_for_it(self):
        self.assertEqual(main(["-w", str(self.env.ws.root), "init", "--product", str(self.env.product),
                               "--reference", "https://vimeo.com/76979871"]), 0)
        cfg = self.env.ws.config()
        self.assertEqual(config.mode(cfg), "reference")
        self.assertNotIn("reference", ids(self.env.ws))
        self.assertEqual(main(["-w", str(self.env.ws.root), "init", "--product", str(self.env.product),
                               "--reference", "none"]), 0)
        self.assertEqual(config.mode(self.env.ws.config()), "autonomous")

    def test_v4_workspaces_keep_their_mode(self):
        cfg = json.loads(self.env.ws.config_path.read_text())
        cfg.pop("reference", None)
        cfg["inspiration"] = {"url": "https://www.youtube.com/watch?v=abcdefghijk"}
        self.env.ws.config_path.write_text(json.dumps(cfg))
        got = self.env.ws.config()
        self.assertEqual(config.mode(got), "reference")
        self.assertEqual(config.reference_source(got), "https://www.youtube.com/watch?v=abcdefghijk")


@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class ReferenceFailures(unittest.TestCase):
    """An inaccessible or failing reference stops the run; nothing is invented."""

    def setUp(self):
        self.env = Env()

    def tearDown(self):
        self.env.close()

    def test_an_inaccessible_url_produces_no_breakdown(self):
        script = fake_watch_script(self.env.tmp / "broken", fail=True)
        with self.assertRaises(PromoError) as cm:
            watcher.watch(self.env.ws, "https://vimeo.com/1", script=script)
        self.assertIn("Video unavailable", str(cm.exception))  # the real cause, surfaced
        self.assertIn("No analysis is invented", cm.exception.hint)
        for p in (self.env.ws.evidence, self.env.ws.root / "reference" / "breakdown.json",
                  self.env.ws.root / "CREATIVE_DIRECTION.md"):
            self.assertFalse(p.exists(), p)

    def test_a_failed_youtube_download_tries_the_fallback_then_explains(self):
        script = fake_watch_script(self.env.tmp / "broken", fail=True)
        with mock.patch.object(watcher, "_fallback_download", return_value=None) as fb:
            with self.assertRaises(PromoError):
                watcher.watch(self.env.ws, "https://youtu.be/abcdefghijk", script=script)
        fb.assert_called_once()

    def test_missing_watch_installation_is_detected(self):
        with mock.patch.dict(os.environ, {"PROMO_WATCH_SKILL_DIR": "/nonexistent"}), \
                mock.patch.object(Path, "home", return_value=self.env.tmp):
            with self.assertRaises(PromoError) as cm:
                watcher.find_watch_skill()
        self.assertIn("not installed", str(cm.exception))
        self.assertIn("/plugin install watch@claude-video", cm.exception.hint)


class RunConfiguration(unittest.TestCase):
    def setUp(self):
        self.env = Env()

    def tearDown(self):
        self.env.close()

    def _init(self, *extra) -> int:
        return main(["-w", str(self.env.ws.root), "init", "--product", str(self.env.product), *extra])

    def test_the_three_audio_choices_map_to_one_policy(self):
        want = {"voiceover": (True, True), "effects": (False, True), "silent": (False, False)}
        for choice, (vo, fx) in want.items():
            extra = ["--provider", "files"] if choice == "voiceover" else []
            self.assertEqual(self._init("--audio", choice, *extra), 0)
            a = self.env.ws.config()["audio"]
            self.assertEqual((a["voiceover"], a["soundEffects"], a["music"]), (vo, fx, False), choice)
            self.assertEqual(config.audio_mode(self.env.ws.config()), choice)
            stored = json.loads(self.env.ws.config_path.read_text())["audio"]
            self.assertIs(stored["music"], False, "the persisted file says music:false explicitly")

    def test_music_can_never_be_enabled(self):
        for bad in ({"music": True}, {"music": "ambient"}, {"music": None}, {"music": 1}):
            cfg = json.loads(self.env.ws.config_path.read_text())
            cfg["audio"] = {"voiceover": False, "soundEffects": True, **bad}
            self.env.ws.config_path.write_text(json.dumps(cfg))
            with self.assertRaises(PromoError, msg=bad) as cm:
                self.env.ws.config()
            self.assertIn("music", str(cm.exception))

    def test_invalid_audio_configurations_are_rejected(self):
        for bad, why in (({"voiceover": True, "soundEffects": False}, "not one of the offered"),
                         ({"voiceover": "yes", "soundEffects": True}, "true or false"),
                         ({"voiceover": False, "soundEffects": True, "bed": "pad"}, "unknown audio setting")):
            cfg = json.loads(self.env.ws.config_path.read_text())
            cfg["audio"] = {**bad, "music": False}
            self.env.ws.config_path.write_text(json.dumps(cfg))
            with self.assertRaises(PromoError, msg=bad) as cm:
                self.env.ws.config()
            self.assertIn(why, str(cm.exception))
        with self.assertRaises(SystemExit):  # argparse refuses anything but the three modes
            self._init("--audio", "music")

    def test_choosing_effects_or_silent_turns_the_voice_off(self):
        self._init("--audio", "effects")
        self.assertEqual(self.env.ws.config()["voice"]["provider"], "none")

    def test_config_holds_no_secret_values(self):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-SECRETVALUE123"}):
            self._init("--audio", "voiceover", "--provider", "openrouter", "--formats", "16:9")
        self.assertNotIn("SECRETVALUE", self.env.ws.config_path.read_text())


class OpeningQuestions(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.ws = self.env.ws
        write_json(self.ws.scan, analyzer.scan(self.env.product, exclude=self.ws.root))

    def tearDown(self):
        self.env.close()

    def _init(self, *extra) -> int:
        return main(["-w", str(self.ws.root), "init", "--product", str(self.env.product), *extra])

    def test_a_fresh_run_asks_reference_first_then_audio(self):
        cfg = json.loads(self.ws.config_path.read_text())
        cfg["decided"] = []
        self.ws.config_path.write_text(json.dumps(cfg))
        got = ids(self.ws)
        self.assertEqual(got[:2], ["reference", "audio"])
        q = questions.plan(self.ws, NO_KEYS)[1]
        self.assertIn("There will be no background music", q["question"])
        self.assertEqual([o["value"] for o in q["options"]], ["voiceover", "effects", "silent"])

    def test_nothing_supplied_up_front_is_asked_again(self):
        self._init("--reference", "none", "--audio", "silent", "--formats", "16:9", "store-portrait",
                   "--runtime", "30-45", "--name", "Tallyboard")
        self.assertEqual(ids(self.ws), [])

    def test_product_facts_in_the_repo_are_not_asked(self):
        cfg = json.loads(self.ws.config_path.read_text())
        cfg["product"]["name"], cfg["decided"] = None, []
        self.ws.config_path.write_text(json.dumps(cfg))
        self.assertNotIn("product", ids(self.ws), "README states name and purpose")
        self.assertNotIn("assets", ids(self.ws), "the repo has screenshots and a logo")

    def test_missing_product_data_is_asked_not_invented(self):
        bare = self.env.tmp / "bare"
        (bare / "src").mkdir(parents=True)
        (bare / "src" / "main.py").write_text("print('hi')\n")
        ws = config.Workspace.at(bare / "promo")
        config.init_workspace(ws, product_root=bare)
        write_json(ws.scan, analyzer.scan(bare, exclude=ws.root))
        got = ids(ws)
        self.assertIn("product", got)
        self.assertIn("assets", got)

    def test_runtime_is_not_asked_when_a_reference_sets_it(self):
        self._init("--reference", "https://vimeo.com/76979871")
        self.assertNotIn("runtime", ids(self.ws))
        self._init("--reference", "none")
        self.assertIn("runtime", ids(self.ws))

    def test_provider_question_only_when_it_cannot_be_inferred(self):
        self._init("--audio", "voiceover")
        one = {**NO_KEYS, "OPENAI_API_KEY": "x"}
        both = {**one, "OPENROUTER_API_KEY": "y"}
        self.assertNotIn("provider", ids(self.ws, one), "one configured provider is used")
        self.assertIn("provider", ids(self.ws, both), "two configured providers → ask which")
        q = next(q for q in questions.plan(self.ws, NO_KEYS) if q["id"] == "provider")
        self.assertIn("no voice API key is configured", q["question"])
        self._init("--audio", "effects")
        self.assertNotIn("provider", ids(self.ws, both), "no narration → no provider question")


class VoiceProviders(unittest.TestCase):
    def test_auto_uses_the_only_configured_provider(self):
        self.assertEqual(providers.resolve("auto", {"OPENAI_API_KEY": "k"}).provider, "openai")
        self.assertEqual(providers.resolve("auto", {"OPENROUTER_API_KEY": "k"}).provider, "openrouter")

    def test_ambiguity_and_absence_are_never_resolved_silently(self):
        both = providers.resolve("auto", {"OPENAI_API_KEY": "a", "OPENROUTER_API_KEY": "b"})
        self.assertIsNone(both.provider)
        self.assertTrue(both.ambiguous)
        cfg = {"voice": {"provider": "auto"}}
        for env in ({"OPENAI_API_KEY": "a", "OPENROUTER_API_KEY": "b"}, {}):
            with self.assertRaises(PromoError):
                providers.pick(cfg, env)  # never falls back to `say`

    def test_an_explicit_provider_without_its_key_fails_and_names_the_variable(self):
        with self.assertRaises(PromoError) as cm:
            providers.pick({"voice": {"provider": "openai"}}, {"OPENROUTER_API_KEY": "x"})
        self.assertIn("OPENAI_API_KEY", str(cm.exception))
        self.assertIn("never paste keys into chat", cm.exception.hint)

    def test_blank_keys_do_not_count(self):
        self.assertEqual(providers.configured_api_providers({"OPENAI_API_KEY": "  "}), [])


if __name__ == "__main__":
    unittest.main()
