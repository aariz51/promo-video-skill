"""The engineering checklist is data: a PASS row without evidence is a false claim."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

CHECKLIST = Path(__file__).resolve().parents[1] / "docs" / "implementation-checklist.md"
STATUSES = {"NOT_STARTED", "IN_PROGRESS", "BLOCKED", "PASS", "FAIL"}


def rows() -> list[dict]:
    out = []
    for line in CHECKLIST.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and re.fullmatch(r"[A-Z]+(-[A-Z0-9]+)+", cells[0]):
            out.append(dict(zip(("id", "req", "where", "evidence", "status", "blocker"), cells)))
    return out


class Checklist(unittest.TestCase):
    def test_rows_are_well_formed(self):
        rs = rows()
        self.assertGreater(len(rs), 20)
        ids = [r["id"] for r in rs]
        self.assertEqual(len(ids), len(set(ids)), "checklist ids must be unique")
        for r in rs:
            self.assertIn(r["status"], STATUSES, r["id"])

    def test_pass_needs_evidence_and_blocked_needs_a_blocker(self):
        for r in rows():
            if r["status"] == "PASS":
                self.assertTrue(r["evidence"], f"{r['id']} is PASS without evidence")
            if r["status"] == "BLOCKED":
                self.assertTrue(r["blocker"], f"{r['id']} is BLOCKED without a blocker")


if __name__ == "__main__":
    unittest.main()
