-- App-wide structured log table
-- All services write here via shared/logging_db.py
CREATE TABLE IF NOT EXISTS app_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    service_name    TEXT NOT NULL,
    log_level       TEXT NOT NULL,
    message         TEXT NOT NULL,
    metadata        JSONB DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_app_log_timestamp ON app_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_app_log_service ON app_log(service_name);
CREATE INDEX IF NOT EXISTS idx_app_log_level ON app_log(log_level);