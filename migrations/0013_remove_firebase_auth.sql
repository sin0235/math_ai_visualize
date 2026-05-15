DELETE FROM users WHERE password_hash LIKE 'firebase:%';
DROP INDEX IF EXISTS idx_users_firebase_uid;
ALTER TABLE users DROP COLUMN firebase_uid;
