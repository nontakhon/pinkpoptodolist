-- Patch script to add 'is_active' column to the tasks table
-- Run this against your SQLite database using:
-- sqlite3 data/thetask.db < patch_is_active.sql

ALTER TABLE tasks ADD COLUMN is_active BOOLEAN DEFAULT 1;
