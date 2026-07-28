CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    last_active_at timestamptz NOT NULL DEFAULT now()
);

-- content stores Claude's native message content for that turn (either a
-- plain string, or a list of text/tool_use/tool_result blocks) so history
-- can be resent to the Messages API without reshaping.
CREATE TABLE IF NOT EXISTS messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role text NOT NULL,
    content jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
    ON messages (conversation_id, created_at);

-- Append-only: a row per feedback submission, never updated/deleted. role is
-- a snapshot at submission time (see ChatRequest.role's comment in main.py) —
-- never treated as current truth. reason is required for a 'down' rating,
-- matching the mandatory chip-select in MessageFeedback.jsx.
CREATE TABLE IF NOT EXISTS feedback (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id uuid NOT NULL,
    role text NOT NULL,
    rating text NOT NULL CHECK (rating IN ('up', 'down')),
    reason text CHECK (reason IN ('reasonWrongData', 'reasonIncomplete', 'reasonMisunderstood', 'reasonOther')),
    comment text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (rating = 'up' OR reason IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_feedback_message_id
    ON feedback (message_id);
