-- Bronze: raw BCRPData responses exactly as they landed, one row per series and run.
-- Auto Loader only reads files it has not seen before.
CREATE OR REFRESH STREAMING TABLE bronze.series_raw
COMMENT 'Raw BCRPData API responses (envelope + payload), one row per series and ingestion run'
AS SELECT
  *,
  _metadata.file_path AS source_file,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/${catalog}/raw/raw_api/series/',
  format => 'json',
  multiLine => true
);
