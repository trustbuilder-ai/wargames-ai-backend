-- Migration: Add context_message_leaf_id to challenge_evaluations
-- Timestamp: 20251001214625
-- Adds a reference to the leaf message in the message tree that triggered the evaluation
-- Creates a composite unique constraint to ensure one evaluation per context+leaf combination

-- Add context_message_leaf_id column (NOT NULL - required for evaluations)
ALTER TABLE challenge_evaluations
ADD COLUMN context_message_leaf_id INTEGER NOT NULL;

-- Add composite unique constraint on (chat_context_id, context_message_leaf_id)
-- This ensures only one evaluation exists per message leaf in a given context
ALTER TABLE challenge_evaluations
ADD CONSTRAINT uq_chat_context_message_leaf
UNIQUE (chat_context_id, context_message_leaf_id);

-- Add index for efficient queries filtering/joining by message leaf ID
CREATE INDEX idx_challenge_evaluations_context_message_leaf_id
ON challenge_evaluations(context_message_leaf_id);

-- Add comment for documentation
COMMENT ON COLUMN challenge_evaluations.context_message_leaf_id
IS 'ID of the leaf message in the message tree that triggered this evaluation';
