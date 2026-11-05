"""Calculate single-machine, single-product OEE from offline shift records."""

import argparse
import csv
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import re

FIELDS = ("shift", "planned_s", "stop_s", "ideal_cycle_ms", "total", "good")


@dataclass(frozen=True)
class Shift:
    name: str
    planned_s: int
    stop_s: int
    cycle_ms: int
    total: int
    good: int

    def __post_init__(self):
        if not self.name.strip() or not self.name.isprintable() or self.name.strip().casefold() == "total":
            raise ValueError("shift label must be printable, nonempty and different from TOTAL")
        nums = (self.planned_s, self.stop_s, self.cycle_ms, self.total, self.good)
        if any(type(x) is not int or x < 0 for x in nums):
            raise ValueError("times and counts must be nonnegative integers")
        if self.planned_s == 0 or self.cycle_ms == 0:
            raise ValueError("planned_s and ideal_cycle_ms must be positive")
        if self.stop_s > self.planned_s:
            raise ValueError("stop_s exceeds planned_s")
        if self.good > self.total:
            raise ValueError("good exceeds total")
        if self.cycle_ms * self.total > (self.planned_s - self.stop_s) * 1000:
            raise ValueError("ideal production time exceeds run time; check cycle units, counts and stops")


def read_shifts(path):
    """Read a comma-separated UTF-8 file (a UTF-8 BOM is accepted)."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = csv.reader(stream, strict=True)
        if tuple(next(rows, [])) != FIELDS:
            raise ValueError("CSV header must be: " + ",".join(FIELDS))
        result = []
        for row in rows:
            if not row:
                continue
            try:
                if len(row) != len(FIELDS):
                    raise ValueError("expected six comma-separated fields")
                name, *numbers = row
                if not all(re.fullmatch(r"[0-9]{1,12}", x) for x in numbers):
                    raise ValueError("numeric fields must be 1 to 12 digits without signs or separators")
                result.append(Shift(name.strip(), *map(int, numbers)))
            except ValueError as exc:
                raise ValueError(f"CSV line {rows.line_num}: {exc}") from exc
    if not result:
        raise ValueError("no shift rows")
    return result


@dataclass(frozen=True)
class Result:
    planned_ms: int
    stop_ms: int
    speed_loss_ms: int
    reject_loss_ms: int
    good_ms: int

    @property
    def run_ms(self):
        return self.planned_ms - self.stop_ms

    @property
    def ideal_ms(self):
        return self.good_ms + self.reject_loss_ms

    @property
    def availability(self):
        return Fraction(self.run_ms, self.planned_ms)

    @property
    def performance(self):
        return Fraction(self.ideal_ms, self.run_ms) if self.run_ms else None

    @property
    def quality(self):
        return Fraction(self.good_ms, self.ideal_ms) if self.ideal_ms else None

    @property
    def oee(self):
        return Fraction(self.good_ms, self.planned_ms)


def summarize(shifts):
    shifts = tuple(shifts)
    if not shifts:
        raise ValueError("no shift rows")
    if len({s.name.strip() for s in shifts}) != len(shifts):
        raise ValueError("shift labels must be unique")
    if len({s.cycle_ms for s in shifts}) != 1:
        raise ValueError("mixed ideal cycles; run separately by product and baseline")
    planned = 1000 * sum(s.planned_s for s in shifts)
    stops = 1000 * sum(s.stop_s for s in shifts)
    ideal = sum(s.cycle_ms * s.total for s in shifts)
    good = sum(s.cycle_ms * s.good for s in shifts)
    return Result(planned, stops, planned - stops - ideal, ideal - good, good)


def percent(value):
    return "n/a" if value is None else f"{float(100 * value):.2f}%"


def seconds(ms):
    whole, remainder = divmod(ms, 1000)
    return f"{whole}.{remainder:03d}"


def format_result(label, result):
    rates = (result.availability, result.performance, result.quality, result.oee)
    return "\t".join([label, *(percent(value) for value in rates)])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_file", type=Path)
    args = parser.parse_args(argv)
    try:
        shifts = read_shifts(args.csv_file)
        combined = summarize(shifts)
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(2, f"Input error: {exc}\n")
    print("scope\tavailability\tperformance\tquality\tOEE")
    for shift in shifts:
        print(format_result(shift.name, summarize([shift])))
    print(format_result("TOTAL", combined))
    times = (combined.planned_ms, combined.stop_ms, combined.speed_loss_ms,
             combined.reject_loss_ms, combined.good_ms)
    labels = ("planned", "stops", "speed", "rejects", "productive")
    print("Time ledger (s): " + ", ".join(f"{k}={seconds(v)}" for k, v in zip(labels, times)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
