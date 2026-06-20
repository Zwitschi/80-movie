-- Add timezone column to screening_event for local time display
ALTER TABLE screening_event
    ADD COLUMN event_timezone TEXT DEFAULT '';