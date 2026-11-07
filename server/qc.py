"""
Real-time QC for tide gauge water levels.

Implements the QARTOD tests from the U.S. IOOS Manual for Real-Time Quality
Control of Water Level Data, Version 2.1 (March 2021). Nothing here touches the
database: each test takes values and thresholds, and returns a QARTOD flag.

QARTOD and NERRS numbers mean different things (QARTOD 1 = pass, NERRS 1 =
suspect), so a flag must never be read without knowing its scheme.

Test status:
    Run here:        Syntax (implicit), Gross Range, Spike, Rate of Change,
                     Flat Line, Attenuated Signal (once thresholds are set)
    Not run yet:     Timing/Gap, Climatology, Neighbor or Forecast
    Does not apply:  Location (fixed gauge, no position sent),
                     Multi-Variate (no second variable)
"""
from statistics import stdev

PASS = 1
NOT_EVALUATED = 2
SUSPECT = 3
FAIL = 4
MISSING = 9

MANUAL_VERSION = "QARTOD Water Level v2.1 (March 2021)"

# Starting thresholds. The spike, rate and flat line values are the manual's
# examples, which it expects operators to replace with site-specific ones.
DEFAULT_WATER_LEVEL_CONFIG = {
    "cycle_seconds": 360,

    # Gross Range. The sensor reports 300 mm for anything closer, so a mean at
    # or near 300 means the water may really be closer than the reading says.
    "sensor_min_mm": 310,
    "sensor_max_mm": 4999,
    "user_min_m": None,
    "user_max_m": None,

    "spike_low_m": 0.1,
    "spike_high_m": 0.2,

    "rate_n_dev": 3,
    "rate_window_hours": 25,
    "rate_min_samples": 120,

    # The manual's example fails at 5 repeats, but that can hide real readings at
    # slack tide. None keeps this test at suspect until field data says otherwise.
    "flat_suspect_count": 3,
    "flat_fail_count": None,
    "flat_eps_m": 0.001,

    # Attenuated Signal stays off until these are set. The manual's examples
    # (0.5 m and 0.1 m over 12 hours) are too large for small local tides.
    "attenuated_window_hours": 12,
    "attenuated_warn_m": None,
    "attenuated_fail_m": None,

    # Project checks on the window statistics, not QARTOD tests.
    "min_n_used": 600,
    "max_rejected_fraction": 0.10,
    "max_no_target_fraction": 0.10,
}


def is_consecutive(earlier, later, cycle_seconds):
    """True if two timestamps are neighbouring readings, with no mark between them."""
    gap = (later - earlier).total_seconds()
    return 0 < gap <= cycle_seconds * 1.5


def gross_range_test(distance_mm, level_m, cfg):
    if distance_mm <= cfg["sensor_min_mm"] or distance_mm > cfg["sensor_max_mm"]:
        return FAIL

    user_min, user_max = cfg.get("user_min_m"), cfg.get("user_max_m")
    if user_min is not None and level_m < user_min:
        return SUSPECT
    if user_max is not None and level_m > user_max:
        return SUSPECT
    return PASS


def spike_test(before, middle, after, cfg):
    """
    Tests the MIDDLE reading, so it can only run once the next one arrives.

    This is the "differential" form used by ioos_qc, not the manual's average
    of the two neighbours. With the average, one large spike also pushes both
    good readings beside it over the limit, and they would be hidden too.
    """
    rise, fall = middle - before, after - middle
    if rise * fall >= 0:  # A steady rise, fall or step is not a spike
        return PASS

    difference = min(abs(rise), abs(fall))
    if difference > cfg["spike_high_m"]:
        return FAIL
    if difference > cfg["spike_low_m"]:
        return SUSPECT
    return PASS


def rate_of_change_test(level_m, previous_m, window_levels, cfg):
    """The manual defines no fail flag for this test, so it stops at suspect."""
    if previous_m is None or len(window_levels) < cfg["rate_min_samples"]:
        return NOT_EVALUATED
    if abs(level_m - previous_m) > cfg["rate_n_dev"] * stdev(window_levels):
        return SUSPECT
    return PASS


def flat_line_test(level_m, previous_levels, cfg):
    """previous_levels is newest first and holds consecutive readings only."""
    # The small allowance stops float noise turning a 1 mm step into a match.
    eps = cfg["flat_eps_m"] - 1e-9

    def last_n_match(count):
        needed = count - 1
        recent = previous_levels[:needed]
        return len(recent) == needed and all(abs(level_m - v) < eps for v in recent)

    if len(previous_levels) < cfg["flat_suspect_count"] - 1:
        return NOT_EVALUATED
    if cfg["flat_fail_count"] is not None and last_n_match(cfg["flat_fail_count"]):
        return FAIL
    if last_n_match(cfg["flat_suspect_count"]):
        return SUSPECT
    return PASS


def attenuated_signal_test(window_levels, cfg):
    warn, fail = cfg.get("attenuated_warn_m"), cfg.get("attenuated_fail_m")
    if warn is None or fail is None or len(window_levels) < 2:
        return NOT_EVALUATED

    variation = max(window_levels) - min(window_levels)
    if variation < fail:
        return FAIL
    if variation < warn:
        return SUSPECT
    return PASS


def window_checks(stats, cfg):
    """Project checks on the sampling window. These can raise suspect, never fail."""
    n_used = stats["n_used"]
    total = n_used + stats["n_rejected"] + stats["n_no_target"]

    return {
        "few_readings": SUSPECT if n_used < cfg["min_n_used"] else PASS,
        "high_rejection": SUSPECT if stats["n_rejected"] > total * cfg["max_rejected_fraction"] else PASS,
        "no_target_readings": SUSPECT if stats["n_no_target"] > total * cfg["max_no_target_fraction"] else PASS,
        "samples_dropped": SUSPECT if stats["dropped"] else PASS,
        # Compact packets have no room for this count
        "at_minimum_range": NOT_EVALUATED if stats["n_floor"] is None
                            else SUSPECT if stats["n_floor"] > 0 else PASS,
        "sd_zero": SUSPECT if stats["sd_mm"] == 0 else PASS,
    }


def overall_flag(tests):
    """
    Worst result across all tests. A pending test doesn't hold back a reading
    that has otherwise passed, or the newest point would never show as pass.
    """
    results = tests.values()
    if FAIL in results:
        return FAIL
    if SUSPECT in results:
        return SUSPECT
    if PASS in results:
        return PASS
    return NOT_EVALUATED


def evaluate_reading(level_m, distance_mm, stats, history, cfg, backfill):
    """
    Runs the checks available when a reading arrives.

    history: earlier readings, oldest first, as objects with .timestamp, .value
             and .qc_flag, covering the time the tests need.

    Backfilled readings aren't real time under the manual, so they only get the
    checks that depend on nothing but the reading itself.
    """
    tests = {"gross_range": gross_range_test(distance_mm, level_m, cfg)}
    tests.update(window_checks(stats, cfg))

    if backfill:
        return tests

    # Failed readings stay in this list on purpose: dropping them would reset
    # the flat line count every time a stuck sensor reached a fail.
    consecutive = []
    next_time = stats["timestamp"]
    for row in reversed(history):
        if not is_consecutive(row.timestamp, next_time, cfg["cycle_seconds"]):
            break
        consecutive.append(row.value)
        next_time = row.timestamp

    usable = [row.value for row in history if row.qc_flag != FAIL]
    previous_m = consecutive[0] if consecutive else None

    tests["spike"] = NOT_EVALUATED
    tests["rate_of_change"] = rate_of_change_test(level_m, previous_m, usable, cfg)
    tests["flat_line"] = flat_line_test(level_m, consecutive, cfg)
    tests["attenuated_signal"] = attenuated_signal_test(usable + [level_m], cfg)
    return tests
