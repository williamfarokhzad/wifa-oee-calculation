# Calculate OEE from shift logs in Python

Turn a CSV from one machine making one product into availability, performance,
quality and overall equipment effectiveness (OEE). Then reconcile every second
in the planned window as a stop, speed loss, reject loss or productive time.

**Website lesson:** [OEE Calculation in Python: A Worked Shift Example](https://wifarobotics.com/learn/oee-calculation/).

## Run from a new folder

1. Install a supported Python 3.11 or newer from [Python.org](https://www.python.org/downloads/).
2. On this repository's GitHub page, choose **Code → Download ZIP**. Extract it
   and open a terminal in the folder containing `oee.py`.
3. Check `python3 --version` on macOS or Linux. On Windows, use `py -3 --version`
   and replace `python3` with `py -3` in the commands below. The lab uses only
   Python's standard library, so there is no package installation or network call.

```sh
python3 oee.py examples/single-shift.csv
python3 oee.py examples/unequal-shifts.csv
python3 oee.py examples/no-output.csv
python3 -m unittest discover -s tests -v
```

| Input | Expected TOTAL OEE | Check |
| --- | ---: | --- |
| Single shift | 66.67% | 2,400 productive seconds out of 3,600 planned |
| Unequal shifts | 60.00% | 5,400 / 9,000; the unweighted 75% is incorrect for the combined window |
| No output | 0.00% | One window is fully stopped; another has run time but zero parts. Quality is undefined for both. |

The invalid-cycle example is intentional:

```sh
python3 oee.py examples/invalid-cycle.csv
```

It exits with status 2 and reports that ideal production time exceeds run
time. A wrong unit, bad count or incorrect stop total can all produce this
error. Check the inputs instead of capping performance at 100%.

## Bring your own small CSV

```csv
shift,planned_s,stop_s,ideal_cycle_ms,total,good
Trial,600,120,2500,160,150
```

Save as UTF-8 and run `python3 oee.py trial.csv`. Expect 62.50% OEE
(375 ideal good seconds divided by 600 planned seconds). The header must match
exactly. Labels must be unique and printable; `TOTAL` is reserved. Quote labels
that contain commas. All numeric fields use whole digits. Record planned and stop
time in seconds, the ideal cycle in milliseconds per part, and total and first
pass good counts in parts. Every row must describe a distinct, nonoverlapping
window for the same machine, part and cycle baseline. The tool cannot verify
machine identity, timestamps or downtime classification from this file.

`n/a` means a factor has no denominator. No run time leaves performance
undefined; no parts leaves quality undefined. A nonempty planned window can
still have 0% OEE. Entirely unscheduled time belongs outside these inputs.

## Figures and references

The original editable SVGs and WebP figures are in `diagrams/`. To regenerate
them, install Inkscape CLI, DejaVu Sans and Pillow separately, then run
`python3 diagrams/render.py`. Those tools are only needed to redraw the figures.

See [Vorne's OEE calculation guide](https://www.oee.com/calculating-oee/) for the
three factors and [Python's CSV reference](https://docs.python.org/3/library/csv.html)
for the file reader. The included shift logs are invented for teaching. This
project reads files only: it does not connect to equipment, collect telemetry,
establish ideal cycle baselines or claim a site KPI is compliant with a standard.
