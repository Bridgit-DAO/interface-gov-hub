-- Add columns for "show linked ordinal in reader, keep uploaded file + history"
-- Run against existing SQLite DB, e.g.:
--   sqlite3 instance/datatracker.db < scripts/migrate_submission_display_body.sql

ALTER TABLE submission ADD COLUMN displayBodySource VARCHAR(20) DEFAULT 'file';
ALTER TABLE submission ADD COLUMN displayOrdinalId VARCHAR(255);
ALTER TABLE submission ADD COLUMN displayOrdinalContentUrl VARCHAR(500);
ALTER TABLE submission ADD COLUMN displayOrdinalContentType VARCHAR(100);
ALTER TABLE submission ADD COLUMN displaySwitchedAt DATETIME;
ALTER TABLE submission ADD COLUMN displaySwitchedBy VARCHAR(100);
