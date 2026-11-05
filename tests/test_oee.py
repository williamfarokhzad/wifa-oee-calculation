import csv
from fractions import Fraction as F
from pathlib import Path
from random import Random
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from oee import FIELDS, Shift, read_shifts, summarize

ROOT = Path(__file__).resolve().parents[1]


class OeeTests(unittest.TestCase):
    def test_single_shift_by_hand(self):
        r = summarize([Shift("Morning", 3600, 600, 2500, 1000, 960)])
        self.assertEqual((r.availability, r.performance, r.quality, r.oee),
                         (F(5, 6), F(5, 6), F(24, 25), F(2, 3)))
        self.assertEqual((r.stop_ms, r.speed_loss_ms, r.reject_loss_ms, r.good_ms),
                         (600000, 500000, 100000, 2400000))

    def test_unequal_shifts_weighted_by_planned_time(self):
        short, long = read_shifts(ROOT / "examples/unequal-shifts.csv")
        first, second = (summarize([s]).oee for s in (short, long))
        self.assertEqual((first + second) / 2, F(3, 4))
        r = summarize([short, long])
        self.assertEqual(r.oee, F(3, 5))
        self.assertEqual((r.availability, r.performance, r.quality), (F(11, 15), F(9, 11), F(1)))

    def test_performance_and_quality_are_undefined_only_when_denominator_zero(self):
        stopped, empty = read_shifts(ROOT / "examples/no-output.csv")
        a, b = (summarize([s]) for s in (stopped, empty))
        self.assertEqual((a.availability, a.performance, a.quality, a.oee), (0, None, None, 0))
        self.assertEqual((b.availability, b.performance, b.quality, b.oee), (1, 0, None, 0))
        self.assertEqual(summarize([stopped, empty]).speed_loss_ms, 900000)

    def test_all_rejected_defines_zero_quality(self):
        r = summarize([Shift("Rejected", 10, 0, 1000, 10, 0)])
        self.assertEqual((r.availability, r.performance, r.quality, r.oee), (1, 1, 0, 0))
        self.assertEqual(r.reject_loss_ms, 10000)

    def test_preserves_exact_millisecond_losses(self):
        r = summarize([Shift("Fast", 1, 0, 125, 7, 6)])
        self.assertEqual((r.speed_loss_ms, r.reject_loss_ms, r.good_ms), (125, 125, 750))
        self.assertEqual(r.oee, F(3, 4))

    def test_time_ledger_against_independent_part_count_and_rate(self):
        rng = Random(474)
        for i in range(300):
            cycle_ms = rng.choice((125, 500, 1000, 2500, 4000))
            shifts = []
            for j in range(3):
                planned = rng.randint(1, 300)
                stop = rng.randint(0, planned)
                count = rng.randint(0, (planned - stop) * 1000 // cycle_ms)
                good = rng.randint(0, count)
                shifts.append(Shift(f"{i}.{j}", planned, stop, cycle_ms, count, good))
            result = summarize(shifts)
            hours = F(sum(s.planned_s for s in shifts), 3600)
            ideal_parts_per_hour = F(3600000, cycle_ms)
            self.assertEqual(result.oee, sum(s.good for s in shifts) / (hours * ideal_parts_per_hour))
            buckets = (result.stop_ms, result.speed_loss_ms, result.reject_loss_ms, result.good_ms)
            self.assertEqual(sum(buckets), 1000 * sum(s.planned_s for s in shifts))
            self.assertTrue(all(b >= 0 for b in buckets))
            if result.quality is not None:
                self.assertEqual(result.availability * result.performance * result.quality, result.oee)

    def test_bad_physical_inputs_are_rejected(self):
        for args in ((0, 0, 1, 0, 0), (9, 10, 1, 0, 0), (9, 0, 0, 0, 0),
                     (9, 0, 1, 5, 6), (9, 0, 5000, 2, 2), (9, 0, 5, -1, 0),
                     (9, 0, 5.0, 1, 1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                Shift("Bad", *args)

    def test_rejects_mixed_cycle_and_duplicate_labels(self):
        a = Shift("A", 9, 0, 500, 2, 2)
        with self.assertRaisesRegex(ValueError, "mixed ideal"):
            summarize([a, Shift("B", 9, 0, 501, 2, 2)])
        with self.assertRaisesRegex(ValueError, "unique"):
            summarize([a, a])

    def test_invalid_labels_do_not_corrupt_tabular_output(self):
        for label in ("", "Total", "Night\tshift", "Day\nshift"):
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "shift label"):
                Shift(label, 9, 0, 500, 2, 2)

    def test_csv_bom_quoted_label_and_field_count(self):
        with TemporaryDirectory() as tmp:
            f = Path(tmp) / "shift.csv"
            with f.open("w", newline="", encoding="utf-8-sig") as out:
                writer = csv.writer(out)
                writer.writerow(FIELDS)
                writer.writerow(("Shift, A", 20, 0, 500, 10, 9))
            self.assertEqual(read_shifts(f)[0].name, "Shift, A")
            with f.open("a") as out:
                out.write("Broken,1,0,500,1\n")
            with self.assertRaisesRegex(ValueError, "CSV line 3"):
                read_shifts(f)

    def test_cli_error_has_no_partial_score(self):
        p = subprocess.run([sys.executable, str(ROOT / "oee.py"), str(ROOT / "examples/invalid-cycle.csv")],
                           capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(p.stdout, "")
        self.assertIn("ideal production time exceeds run time", p.stderr)

    def test_cli_good_run(self):
        p = subprocess.run([sys.executable, str(ROOT / "oee.py"), str(ROOT / "examples/single-shift.csv")],
                           capture_output=True, text=True, check=True)
        self.assertIn("Morning\t83.33%\t83.33%\t96.00%\t66.67%", p.stdout)
        self.assertIn("speed=500.000, rejects=100.000, productive=2400.000", p.stdout)
