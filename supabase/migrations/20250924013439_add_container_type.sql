-- Migration: Add type column to chat_template_container
-- Timestamp: 20250924013439
-- Adds a type field to categorize containers (e.g., 'challenge', 'tutorial', 'assessment')

-- Add type column with default value for existing rows
ALTER TABLE chat_template_container
ADD COLUMN type TEXT NOT NULL DEFAULT 'challenge';

-- Add index for potential filtering by type
CREATE INDEX idx_chat_template_container_type ON chat_template_container(type);

-- Comment on the new column
COMMENT ON COLUMN chat_template_container.type IS 'Type of container: challenge, tutorial, assessment, etc.';