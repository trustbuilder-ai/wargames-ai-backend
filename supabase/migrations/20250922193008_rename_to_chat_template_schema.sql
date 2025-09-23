-- Migration: Rename tables to chat_template schema and add MessageTree support
-- Timestamp: 20250922193008
-- This migration renames all challenge/tournament tables to chat_template naming
-- and updates all related columns, constraints, and indexes

-- 1. Drop all foreign key constraints first (we'll recreate them with new names)
ALTER TABLE badges DROP CONSTRAINT IF EXISTS fk_badge_challenge;
ALTER TABLE challenges DROP CONSTRAINT IF EXISTS fk_challenge_tournament;
ALTER TABLE user_challenge_contexts DROP CONSTRAINT IF EXISTS fk_context_challenge;
ALTER TABLE user_challenge_contexts DROP CONSTRAINT IF EXISTS fk_context_user;
ALTER TABLE user_tournament_enrollments DROP CONSTRAINT IF EXISTS fk_enrollment_tournament;
ALTER TABLE user_tournament_enrollments DROP CONSTRAINT IF EXISTS fk_enrollment_user;
ALTER TABLE user_badges DROP CONSTRAINT IF EXISTS fk_user_badge_badge;
ALTER TABLE user_badges DROP CONSTRAINT IF EXISTS fk_user_badge_user;
ALTER TABLE challenge_evaluations DROP CONSTRAINT IF EXISTS challenge_evaluation_user_challenge_context_id_fkey;
ALTER TABLE user_challenge_context_messages DROP CONSTRAINT IF EXISTS user_challenge_context_messages_user_challenge_context_id_fkey;

-- 2. Drop unique constraints that will be recreated
ALTER TABLE user_challenge_contexts DROP CONSTRAINT IF EXISTS uq_user_challenge;
ALTER TABLE user_tournament_enrollments DROP CONSTRAINT IF EXISTS uq_user_tournament;

-- 3. Rename tables
ALTER TABLE challenges RENAME TO chat_template;
ALTER TABLE tournaments RENAME TO chat_template_container;
ALTER TABLE user_challenge_contexts RENAME TO user_chat_template_context;
ALTER TABLE user_challenge_context_messages RENAME TO user_chat_template_context_messages;

-- 4. Rename columns to match new table names
ALTER TABLE badges RENAME COLUMN challenge_id TO chat_template_id;
ALTER TABLE chat_template RENAME COLUMN tournament_id TO chat_template_container_id;
ALTER TABLE user_chat_template_context RENAME COLUMN challenge_id TO chat_template_id;
ALTER TABLE user_chat_template_context_messages RENAME COLUMN user_challenge_context_id TO user_chat_template_context_id;
ALTER TABLE challenge_evaluations RENAME COLUMN user_challenge_context_id TO user_chat_template_context_id;

-- 5. Add new columns for MessageTree support
-- Add message_tree column to chat_template (JSONB for schema-less JSON)
ALTER TABLE chat_template ADD COLUMN message_tree JSONB;

-- Add parent_message_id to messages table for hierarchical message support
ALTER TABLE user_chat_template_context_messages
ADD COLUMN parent_message_id INTEGER;

-- 6. Data migration: Convert system_prompt and initial_llm_prompt to MessageTree format
-- Only update rows where message_tree is NULL (ensures one-time execution)

-- Case 1: Both system_prompt and initial_llm_prompt exist
UPDATE chat_template
SET message_tree = jsonb_build_array(
    jsonb_build_object(
        'id', 1,
        'parent_message_id', NULL::integer,
        'message', jsonb_build_object(
            'role', 'system',
            'content', system_prompt,
            'is_tool_call', false
        )
    ),
    jsonb_build_object(
        'id', 2,
        'parent_message_id', 1,
        'message', jsonb_build_object(
            'role', 'assistant',
            'content', initial_llm_prompt,
            'is_tool_call', false
        )
    )
)
WHERE message_tree IS NULL
  AND system_prompt IS NOT NULL
  AND initial_llm_prompt IS NOT NULL;

-- Case 2: Only system_prompt exists
UPDATE chat_template
SET message_tree = jsonb_build_array(
    jsonb_build_object(
        'id', 1,
        'parent_message_id', NULL::integer,
        'message', jsonb_build_object(
            'role', 'system',
            'content', system_prompt,
            'is_tool_call', false
        )
    )
)
WHERE message_tree IS NULL
  AND system_prompt IS NOT NULL
  AND initial_llm_prompt IS NULL;

-- Case 3: Only initial_llm_prompt exists
UPDATE chat_template
SET message_tree = jsonb_build_array(
    jsonb_build_object(
        'id', 1,
        'parent_message_id', NULL::integer,
        'message', jsonb_build_object(
            'role', 'assistant',
            'content', initial_llm_prompt,
            'is_tool_call', false
        )
    )
)
WHERE message_tree IS NULL
  AND system_prompt IS NULL
  AND initial_llm_prompt IS NOT NULL;

-- 7. Drop the old columns after migration
ALTER TABLE chat_template DROP COLUMN IF EXISTS system_prompt;
ALTER TABLE chat_template DROP COLUMN IF EXISTS initial_llm_prompt;

-- 8. Drop user_tournament_enrollments table (no longer needed)
DROP TABLE IF EXISTS user_tournament_enrollments CASCADE;

-- 9. Recreate foreign key constraints with new names
ALTER TABLE badges
ADD CONSTRAINT fk_badge_chat_template
FOREIGN KEY (chat_template_id) REFERENCES chat_template(id) ON DELETE CASCADE;

ALTER TABLE chat_template
ADD CONSTRAINT fk_chat_template_container
FOREIGN KEY (chat_template_container_id) REFERENCES chat_template_container(id) ON DELETE CASCADE;

ALTER TABLE user_chat_template_context
ADD CONSTRAINT fk_context_chat_template
FOREIGN KEY (chat_template_id) REFERENCES chat_template(id) ON DELETE CASCADE;

ALTER TABLE user_chat_template_context
ADD CONSTRAINT fk_context_user
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE challenge_evaluations
ADD CONSTRAINT challenge_evaluation_user_chat_template_context_id_fkey
FOREIGN KEY (user_chat_template_context_id) REFERENCES user_chat_template_context(id) ON DELETE CASCADE;

ALTER TABLE user_chat_template_context_messages
ADD CONSTRAINT user_chat_template_context_messages_user_chat_template_context_id_fkey
FOREIGN KEY (user_chat_template_context_id) REFERENCES user_chat_template_context(id) ON DELETE CASCADE;

ALTER TABLE user_badges
ADD CONSTRAINT fk_user_badge_badge
FOREIGN KEY (badge_id) REFERENCES badges(id) ON DELETE CASCADE;

ALTER TABLE user_badges
ADD CONSTRAINT fk_user_badge_user
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- 10. Recreate unique constraints
ALTER TABLE user_chat_template_context
ADD CONSTRAINT uq_user_chat_template UNIQUE (user_id, chat_template_id);

-- 11. Drop and recreate indexes with new names
-- Drop old indexes
DROP INDEX IF EXISTS idx_badges_challenge_id;
DROP INDEX IF EXISTS idx_challenges_tournament_id;
DROP INDEX IF EXISTS idx_contexts_challenge_id;
DROP INDEX IF EXISTS idx_contexts_user_id;
DROP INDEX IF EXISTS idx_enrollments_tournament_id;
DROP INDEX IF EXISTS idx_enrollments_user_id;
DROP INDEX IF EXISTS idx_user_message_metadata_user_id;

-- Create new indexes with updated names
CREATE INDEX idx_badges_chat_template_id ON badges(chat_template_id);
CREATE INDEX idx_chat_template_container_id ON chat_template(chat_template_container_id);
CREATE INDEX idx_user_chat_template_context_chat_template_id ON user_chat_template_context(chat_template_id);
CREATE INDEX idx_user_chat_template_context_user_id ON user_chat_template_context(user_id);
CREATE INDEX idx_user_chat_template_context_messages_context_id ON user_chat_template_context_messages(user_chat_template_context_id);

-- Add index for the new parent_message_id column
CREATE INDEX idx_user_chat_template_context_messages_parent_id
ON user_chat_template_context_messages(parent_message_id);

-- Keep existing indexes that don't need renaming
-- idx_tournaments_dates -> automatically follows table rename to chat_template_container
-- idx_user_badges_badge_id -> stays the same
-- idx_user_badges_user_id -> stays the same
-- idx_users_sub_id -> stays the same
-- idx_user_message_metadata_created_at -> automatically follows table rename

-- Migration complete