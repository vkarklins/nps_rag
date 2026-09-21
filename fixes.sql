-- fixes.sql
--
-- Manual corrections for source-data errors in the `incidents` table. The scraper
-- (data/incidents.jsonl) reproduces the source page as-is, so these have to be re-applied
-- whenever load_incidents.py reloads the table.
--
-- Order after a reload:
--   1. poetry run python -m rag_nps.load_incidents
--   2. psql -f fixes.sql            (this file)
--   3. poetry run python -m rag_nps.get_embeddings
--
-- Safe to run more than once: each UPDATE only matches rows that still have the bad value,
-- so on an already-fixed table it changes nothing ("UPDATE 0"). When a row IS fixed, its
-- embedding is set to NULL because the text it was built from has changed; get_embeddings
-- will re-embed just those rows. (On a table that was fixed before embedding, nothing
-- matches and no existing embeddings are touched.)
--
-- Not fixed on purpose: noca-00100 (May 15, 2019, a servicewide Weekly Weather Impacts
-- Update) has a genuine date that simply sits out of chronological order on the source page.

BEGIN;

-- 1. Four entries the source dates "January 7, 2027". They describe late-December 2025
--    events, so the year is really 2026. header_lines[1] is the date line (Postgres arrays
--    are 1-indexed).
UPDATE incidents
SET date_raw      = 'January 7, 2026',
    incident_date = DATE '2026-01-07',
    header_lines[1] = 'January 7, 2026',
    embedding     = NULL
WHERE incident_id IN ('bibe-00245', 'cong-00016', 'grsm-00587', 'olym-00356')
  AND date_raw = 'January 7, 2027';

-- 2. dena-00019: OCR errors in the source, "19B9" for 1989 and "99-37" for 89-37.
UPDATE incidents
SET date_raw        = 'Thursday, March 9, 1989',
    incident_date   = DATE '1989-03-09',
    incident_number = '89-37',
    title           = '89-37 - Denali - Follow-up on Missing Climbers',
    header_lines    = ARRAY['Thursday, March 9, 1989',
                            '89-37 - Denali - Follow-up on Missing Climbers'],
    embedding       = NULL
WHERE incident_id = 'dena-00019'
  AND date_raw = 'Thursday, March 9, 19B9';

-- 3. Every GAAR (Gates of the Arctic) row has park_name '...National Park and Preserv'. The typo
--    is in the source page itself: its <title> is cut off at 45 characters (see page_title for
--    gaar in data/parks.json), and the scraper copies the title as-is. park_name is the first
--    line of the embedded text, so the embeddings are reset like the fixes above.
UPDATE incidents
SET park_name = 'Gates of the Arctic National Park and Preserve',
    embedding = NULL
WHERE park_code = 'GAAR'
  AND park_name = 'Gates of the Arctic National Park and Preserv';

COMMIT;

-- Show the corrected rows.
SELECT incident_id, date_raw, incident_date, incident_number, title, header_lines,
       embedding IS NULL AS needs_embedding
FROM incidents
WHERE incident_id IN ('bibe-00245', 'cong-00016', 'grsm-00587', 'olym-00356', 'dena-00019')
ORDER BY incident_id;

-- Show the GAAR rows: one park_name, and how many still need embedding.
SELECT park_name, count(*) AS incidents, count(*) FILTER (WHERE embedding IS NULL) AS needs_embedding
FROM incidents
WHERE park_code = 'GAAR'
GROUP BY park_name;
