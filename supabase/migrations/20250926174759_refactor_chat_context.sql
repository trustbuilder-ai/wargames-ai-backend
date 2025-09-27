-- Migration: Refactor user_chat_template_context to chat_context
-- Timestamp: 20250926174759
-- This migration:
-- 1. Renames user_chat_template_context table to chat_context
-- 2. Removes columns: last_message_id, processing_started_at, processing_token, last_message_version
-- 3. Adds message_tree column (JSONB) to match chat_template table structure
-- 4. Drops the user_chat_template_context_messages table
-- 5. Updates all related foreign keys, constraints, and indexes

-- 1. Drop foreign key constraints that reference the old table
ALTER TABLE challenge_evaluations
  DROP CONSTRAINT IF EXISTS challenge_evaluation_user_chat_template_context_id_fkey;

ALTER TABLE user_chat_template_context_messages
  DROP CONSTRAINT IF EXISTS user_chat_template_context_messages_user_chat_template_context_id_fkey;

-- 2. Drop the unique constraint (will be recreated with new name)
ALTER TABLE user_chat_template_context
  DROP CONSTRAINT IF EXISTS uq_user_chat_template;

-- 3. Drop indexes that will be recreated with new names
DROP INDEX IF EXISTS idx_user_chat_template_context_chat_template_id;
DROP INDEX IF EXISTS idx_user_chat_template_context_user_id;
DROP INDEX IF EXISTS idx_user_chat_template_context_messages_context_id;
DROP INDEX IF EXISTS idx_user_chat_template_context_messages_parent_id;

-- 4. Rename the table
ALTER TABLE user_chat_template_context RENAME TO chat_context;

-- 5. Remove unnecessary columns
ALTER TABLE chat_context
  DROP COLUMN IF EXISTS last_message_id,
  DROP COLUMN IF EXISTS processing_started_at,
  DROP COLUMN IF EXISTS processing_token,
  DROP COLUMN IF EXISTS last_message_version;

-- 6. Add message_tree column (JSONB type to match chat_template table)
ALTER TABLE chat_context
  ADD COLUMN message_tree JSONB;

-- 7. Drop the user_chat_template_context_messages table
DROP TABLE IF EXISTS user_chat_template_context_messages CASCADE;

-- 8. Update column names in challenge_evaluations table to match new naming
ALTER TABLE challenge_evaluations
  RENAME COLUMN user_chat_template_context_id TO chat_context_id;

-- 9. Recreate foreign key constraints with new names
ALTER TABLE challenge_evaluations
  ADD CONSTRAINT fk_evaluation_chat_context
  FOREIGN KEY (chat_context_id) REFERENCES chat_context(id) ON DELETE CASCADE;

-- Note: The existing foreign keys on chat_context table don't need to be recreated
-- as they follow the table rename automatically:
-- - fk_context_chat_template (chat_template_id -> chat_template)
-- - fk_context_user (user_id -> users)

-- 10. Recreate unique constraint with new name
ALTER TABLE chat_context
  ADD CONSTRAINT uq_user_chat_template UNIQUE (user_id, chat_template_id);

-- 11. Create new indexes with updated names
CREATE INDEX idx_chat_context_chat_template_id ON chat_context(chat_template_id);
CREATE INDEX idx_chat_context_user_id ON chat_context(user_id);

-- 12. Add index on message_tree column for JSONB queries (optional but recommended)
CREATE INDEX idx_chat_context_message_tree ON chat_context USING gin(message_tree);

-- 13. Add comments for documentation
COMMENT ON TABLE chat_context IS 'Stores user-specific context for chat templates including message history';
COMMENT ON COLUMN chat_context.message_tree IS 'Hierarchical message tree structure in JSONB format, matching chat_template.message_tree structure';

-- Migration complete