-- Migration: Make chat_template_container dates nullable
-- Timestamp: 20250924021209
-- Allows containers to have open-ended date ranges

-- Make start_date and end_date nullable
ALTER TABLE chat_template_container
ALTER COLUMN start_date DROP NOT NULL,
ALTER COLUMN end_date DROP NOT NULL;

-- Add comment explaining the nullable behavior
COMMENT ON COLUMN chat_template_container.start_date IS 'Container start date. NULL means no start restriction (always started)';
COMMENT ON COLUMN chat_template_container.end_date IS 'Container end date. NULL means no end restriction (never ends)';