"""
Tide gauge ingest. Every packet is kept as sent in gauge_readings. Only
water_level and the health values go on to sensor_data, which is what the
dashboard graphs, so the QC statistics are never plotted.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.dialects.postgresql import insert

from .database import db
from .models import GaugeDatum, GaugeReading, QcAssessment, QcConfig, SensorData, get_or_create_parameter
from .qc import (DEFAULT_WATER_LEVEL_CONFIG, MANUAL_VERSION, NOT_EVALUATED, SUSPECT, evaluate_reading,
                 is_consecutive, overall_flag, spike_test)

EPOCH = datetime(1970, 1, 1)

# A packet leaves after its window closes at mark+90 s, and at worst by mark+180 s.
TYPICAL_ARRIVAL_DELAY = timedelta(seconds=135)

STATUS_LOST_POWER = 0x01
STATUS_DROPPED = 0x02
STATUS_BACKFILL = 0x08

REQUIRED_FIELDS = ('distance_mm', 'sd_mm', 'n_used', 'n_rejected', 'n_no_target', 'status_raw')


@dataclass
class PendingReading:
    """What the route needs to finish storing one packet."""
    measurements: dict = field(default_factory=dict)
    stop_reason: Optional[str] = None
    flag: Optional[int] = None
    tests: Optional[dict] = None
    config: Optional[QcConfig] = None
    cfg: Optional[dict] = None
    history: list = field(default_factory=list)
    backfill: bool = False
    water_level_entry: Optional[SensorData] = None


def get_datum(sensor_id, timestamp):
    return GaugeDatum.query.filter(
        GaugeDatum.sensor_id == sensor_id,
        GaugeDatum.valid_from <= timestamp,
        (GaugeDatum.valid_to.is_(None)) | (GaugeDatum.valid_to > timestamp)
    ).first()


def get_active_config(sensor_id, parameter_id):
    config = QcConfig.query.filter_by(sensor_id=sensor_id, parameter_id=parameter_id, valid_to=None).first()
    if not config:
        config = QcConfig(sensor_id=sensor_id, parameter_id=parameter_id,
                          thresholds=dict(DEFAULT_WATER_LEVEL_CONFIG), manual_version=MANUAL_VERSION,
                          valid_from=datetime(1970, 1, 1))
        db.session.add(config)
        db.session.flush()
    return {**DEFAULT_WATER_LEVEL_CONFIG, **config.thresholds}, config


def get_history(sensor_id, parameter_id, timestamp, hours):
    return (
        SensorData.query
        .filter(SensorData.sensor_id == sensor_id,
                SensorData.parameter_id == parameter_id,
                SensorData.timestamp >= timestamp - timedelta(hours=hours),
                SensorData.timestamp < timestamp)
        .order_by(SensorData.timestamp)
        .all()
    )


def rebuild_mark_time(received_at, cycles_back, cycle_seconds):
    """
    Compact packets carry no time. A packet always arrives after its own mark
    and before the next, so round down. Rounding to the nearest mark would go
    wrong for a slow send, which can arrive up to 180 s after its mark.
    """
    seconds = int((received_at - EPOCH).total_seconds())
    return EPOCH + timedelta(seconds=seconds - seconds % cycle_seconds - cycles_back * cycle_seconds)


def estimate_mark_time(received_at, cycles_back, cycle_seconds):
    """
    For compact packets from a device that has lost its clock. The device's marks
    no longer line up with real ones, so rounding could put two readings on the
    same mark and drop one as a duplicate. Good to about a minute, not to the mark.
    """
    return received_at - TYPICAL_ARRIVAL_DELAY - timedelta(seconds=cycles_back * cycle_seconds)


def begin_reading(sensor, payload):
    """
    Stores the raw packet and works out what to pass to the ingest loop. Only
    fields named here go any further, so a new codec field can't reach a graph.
    Returns None if the packet isn't a valid tide gauge payload.
    """
    decoded = payload['measurements']
    received_at = datetime.utcnow()
    time_source = decoded.get('time_source', 'device')

    missing_time = time_source == 'device' and decoded.get('timestamp') is None
    missing_cycles = time_source == 'server' and decoded.get('cycles_back') is None
    if any(decoded.get(key) is None for key in REQUIRED_FIELDS) or missing_time or missing_cycles:
        print(f"Invalid tide gauge payload from '{sensor.name}'")
        return None

    parameter = get_or_create_parameter('water_level')
    cfg, config = get_active_config(sensor.id, parameter.id)

    status = int(decoded['status_raw'])
    lost_power = bool(status & STATUS_LOST_POWER)

    if time_source == 'device':
        timestamp = decoded['timestamp']
    elif lost_power:
        timestamp = estimate_mark_time(received_at, decoded['cycles_back'], cfg['cycle_seconds'])
    else:
        timestamp = rebuild_mark_time(received_at, decoded['cycles_back'], cfg['cycle_seconds'])

    # A lost clock only makes a device-reported time useless. Compact packets
    # never use that time, because cycles_back is a difference between two clock
    # readings and the server supplies the reference point.
    time_ok = not (lost_power and time_source == 'device')
    backfill = bool(status & STATUS_BACKFILL)

    # The device sends a distance of 0 when it had nothing to average.
    has_distance = decoded['n_used'] > 0 and decoded['distance_mm'] > 0
    distance_mm = int(decoded['distance_mm']) if has_distance else None
    datum = get_datum(sensor.id, timestamp) if time_ok else None

    inserted = db.session.execute(
        insert(GaugeReading)
        .values(sensor_id=sensor.id, mark_time=timestamp, received_at=received_at,
                fcnt=payload.get('fcnt'), distance_mm=distance_mm, sd_mm=decoded['sd_mm'],
                n_used=decoded['n_used'], n_rejected=decoded['n_rejected'],
                n_no_target=decoded['n_no_target'], n_floor=decoded.get('n_floor'),
                battery_v=decoded.get('battery'), board_temp_c=decoded.get('board_temp_c'),
                rssi=decoded.get('rssi'), snr=decoded.get('snr'), status=status,
                queue_depth=decoded.get('queue_depth'), backfill=backfill,
                time_source=time_source, degraded=bool(decoded.get('degraded')), time_ok=time_ok,
                datum_id=datum.id if datum else None)
        .on_conflict_do_nothing(index_elements=['sensor_id', 'mark_time'], index_where=GaugeReading.time_ok)
        .returning(GaugeReading.id)
    ).first()

    if inserted is None:
        return PendingReading(stop_reason='Duplicate reading ignored')

    # A wrong clock means a wrong mark time, so this reading can't go on a timeline.
    if not time_ok:
        return PendingReading(stop_reason='Reading quarantined: clock lost power')

    measurements = {'timestamp': timestamp, 'board_temperature': decoded.get('board_temp_c')}

    # The value is a placeholder until the hardware can measure it, so it stays
    # out of the health panel. The raw value is still in gauge_readings.
    if decoded.get('battery_valid'):
        measurements['battery'] = decoded.get('battery')

    # Signal strength describes the moment of delivery, not this reading's mark time.
    if not backfill:
        measurements['rssi'] = decoded.get('rssi')
        measurements['snr'] = decoded.get('snr')

    pending = PendingReading(measurements=measurements, backfill=backfill)

    if distance_mm is None:
        return pending

    if datum is None:
        print(f"Warning: Tide gauge '{sensor.name}' has no NAVD88 elevation for {timestamp}; "
              "raw reading kept, water level not calculated.")
        return pending

    level_m = datum.elevation_m - distance_mm / 1000
    measurements['water_level'] = level_m

    history = [] if backfill else get_history(sensor.id, parameter.id, timestamp, cfg['rate_window_hours'])

    stats = {key: decoded[key] for key in ('sd_mm', 'n_used', 'n_rejected', 'n_no_target')}
    stats.update(timestamp=timestamp, n_floor=decoded.get('n_floor'), dropped=bool(status & STATUS_DROPPED))

    pending.tests = evaluate_reading(level_m, distance_mm, stats, history, cfg, backfill)
    if lost_power:
        pending.tests['time_estimated'] = SUSPECT
    pending.flag = overall_flag(pending.tests)
    pending.config = config
    pending.cfg = cfg
    pending.history = history
    return pending


def finish_reading(pending):
    """Records the QC result, then runs the spike test on the previous reading."""
    entry = pending.water_level_entry
    if entry is None:
        return

    db.session.add(QcAssessment(sensor_data_id=entry.id, scheme='qartod', source='realtime',
                                flag=pending.flag, tests=pending.tests, config_id=pending.config.id))

    if not pending.backfill:
        apply_spike_result(pending, entry)


def apply_spike_result(pending, entry):
    """
    The spike test judges the previous reading, so its result arrives one
    reading late. This is the one case where a real-time flag changes.
    """
    if len(pending.history) < 2:
        return

    before, middle = pending.history[-2], pending.history[-1]
    cycle = pending.cfg['cycle_seconds']
    if not (is_consecutive(before.timestamp, middle.timestamp, cycle)
            and is_consecutive(middle.timestamp, entry.timestamp, cycle)):
        return

    assessment = QcAssessment.query.filter_by(sensor_data_id=middle.id, scheme='qartod',
                                              source='realtime').first()

    # Backfilled readings have no pending spike result, and stay that way.
    if not assessment or assessment.tests.get('spike') != NOT_EVALUATED:
        return

    tests = dict(assessment.tests)
    tests['spike'] = spike_test(before.value, middle.value, entry.value, pending.cfg)
    assessment.tests = tests
    assessment.flag = overall_flag(tests)
    middle.qc_flag = assessment.flag
