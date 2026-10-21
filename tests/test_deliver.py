"""`promo deliver`: what goes in, and when it refuses."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import Env  # noqa: E402

from promo_engine import deliver
from promo_engine.util import PromoError, write_json


class Refusals(unittest.TestCase):
    def setUp(self):
        self.env = Env().with_artifacts()

    def tearDown(self):
        self.env.close()

    def test_needs_a_passing_qa_and_a_final_film(self):
        with self.assertRaises(PromoError) as cm:
            deliver.deliver(self.env.ws)
        self.assertIn("no QA result", str(cm.exception))
        write_json(self.env.ws.qa_dir / "validation.json", {"result": "FAIL"})
        with self.assertRaises(PromoError) as cm:
            deliver.deliver(self.env.ws)
        self.assertIn("QA did not pass", str(cm.exception))
        write_json(self.env.ws.qa_dir / "validation.json", {"result": "PASS"})
        self.env.ws.out_dir.mkdir(parents=True, exist_ok=True)
        (self.env.ws.out_dir / "promo-16x9-draft.mp4").write_bytes(b"x")
        with self.assertRaises(PromoError) as cm:
            deliver.deliver(self.env.ws)
        self.assertIn("no final-quality film", str(cm.exception))

    def test_never_writes_into_a_folder_it_did_not_create(self):
        foreign = self.env.tmp / "client-folder"
        foreign.mkdir()
        (foreign / "contract.pdf").write_text("keep me")
        with self.assertRaises(PromoError) as cm:
            deliver.deliver(self.env.ws, out=foreign)
        self.assertIn("refusing to write into it", str(cm.exception))
        self.assertEqual((foreign / "contract.pdf").read_text(), "keep me")


if __name__ == "__main__":
    unittest.main()
