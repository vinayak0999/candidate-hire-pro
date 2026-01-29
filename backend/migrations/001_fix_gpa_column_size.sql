-- Migration: Fix GPA column size (VARCHAR(20) -> VARCHAR(100))
-- Run this on your database to fix the "value too long" error for GPA field
-- Date: 2026-01-29

-- Check current column size
-- SELECT character_maximum_length FROM information_schema.columns
-- WHERE table_name = 'education' AND column_name = 'gpa';

-- Alter the column to allow longer GPA values like "9.25 (3rd Rank in Class)"
ALTER TABLE education ALTER COLUMN gpa TYPE VARCHAR(100);

-- Verify the change
-- SELECT character_maximum_length FROM information_schema.columns
-- WHERE table_name = 'education' AND column_name = 'gpa';
