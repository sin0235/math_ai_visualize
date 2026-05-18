ALTER TABLE chat_messages ADD COLUMN message_type TEXT NOT NULL DEFAULT 'text';
ALTER TABLE chat_messages ADD COLUMN image_url TEXT;
ALTER TABLE chat_messages ADD COLUMN image_public_id TEXT;
ALTER TABLE chat_messages ADD COLUMN image_width INTEGER;
ALTER TABLE chat_messages ADD COLUMN image_height INTEGER;
ALTER TABLE chat_messages ADD COLUMN image_bytes INTEGER;
ALTER TABLE chat_messages ADD COLUMN image_format TEXT;
ALTER TABLE chat_messages ADD COLUMN image_original_name TEXT;
