from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

db = SQLAlchemy()

# Arbitrary fixed key: only one process at a time may run the startup migration.
MIGRATION_LOCK_KEY = 727401


def run_migrations():
    """
    Applies schema changes that db.create_all() cannot make to existing tables.
    Every statement is safe to repeat, because this runs on every startup.
    """
    with db.engine.begin() as conn:
        conn.execute(text("SET LOCAL lock_timeout = '10s'"))
        conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS qc_flag SMALLINT"))
        # Sensors from before test devices existed are all live
        conn.execute(text("ALTER TABLE sensors ADD COLUMN IF NOT EXISTS testing BOOLEAN NOT NULL DEFAULT FALSE"))

        # Give tide gauges that already have an elevation their first datum.
        conn.execute(text("""
            INSERT INTO gauge_datums (sensor_id, elevation_m, valid_from)
            SELECT s.id, s.navd88_elevation, TIMESTAMP '1970-01-01'
            FROM sensors s
            WHERE s.device_type = 'tide_gauge'
              AND s.navd88_elevation IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM gauge_datums d WHERE d.sensor_id = s.id)
        """))


def init_db(server):
    db.init_app(server)
    with server.app_context():
        db.create_all()
        run_migrations()
