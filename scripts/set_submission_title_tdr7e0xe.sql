-- Run against the SAME SQLite file the Flask app uses.
--
-- gov-hub-prod (ietf_data_viewer_simple.py): instance/datatracker.db (production)
--   or instance_dev/datatracker_dev.db if FLASK_ENV=development
-- gov-hub-dev modular app: check SQLALCHEMY_DATABASE_URI / instance path in config.
--
-- Example (production monolith, repo root = ~/gov-hub-prod):
--   sqlite3 instance/datatracker.db < scripts/set_submission_title_tdr7e0xe.sql
--
-- If you see "no such table: submission", wrong DB file or empty DB:
--   sqlite3 instance/datatracker.db ".tables"
--
UPDATE submission
SET title = 'DP2 - Participant Agency & Empowerment'
WHERE id = 'tdr7e0xe';
