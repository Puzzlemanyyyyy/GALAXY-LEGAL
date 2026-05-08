-- Galaxy Legal — 0004_storage_size.sql
-- Raise the per-file upload limit on the `legal-documents` Storage bucket
-- from the Supabase default (50 MB) to 100 MB so that scanned-PDF
-- expedientes fit comfortably without triggering the bucket cap.
--
-- IDEMPOTENT: re-running this script just sets the same value again.
-- 104857600 = 100 * 1024 * 1024 (binary MB, matches Supabase Studio's display).
--
-- The application-side limit is enforced by FastAPI BEFORE this storage
-- check kicks in (see `MAX_DOCUMENT_SIZE_MB` in backend/config.py and the
-- 413 guard in routes/documents.py:upload_document). Keep them aligned.

update storage.buckets
   set file_size_limit = 104857600
 where id = 'legal-documents';
