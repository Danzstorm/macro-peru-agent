-- Silver: one row per (series, period), always with the latest value received.
-- Each file holds a single series, so values are never mapped by position
-- (the API reorders series when several are requested together).

CREATE TEMPORARY VIEW series_points AS
WITH exploded AS (
  SELECT
    codigo,
    alias,
    CAST(fetched_at AS TIMESTAMP) AS fetched_at,
    source_file,
    explode(payload.periods) AS p
  FROM STREAM(bronze.series_raw)
),
labeled AS (
  SELECT *, p.name AS periodo_label, p.`values`[0] AS raw_value, split(p.name, '\\.') AS parts
  FROM exploded
)
SELECT
  codigo,
  alias,
  periodo_label,
  -- Period label -> first day of the period. September is "Sep" in monthly
  -- series and "Set" in daily series.
  CASE
    WHEN size(parts) = 3 THEN make_date(  -- daily: 02.Ene.26
      2000 + int(parts[2]),
      element_at(map('ene',1,'feb',2,'mar',3,'abr',4,'may',5,'jun',6,'jul',7,'ago',8,
                     'sep',9,'set',9,'oct',10,'nov',11,'dic',12), lower(parts[1])),
      int(parts[0]))
    WHEN size(parts) = 2 AND parts[0] RLIKE '^T[1-4]$' THEN make_date(  -- quarterly: T1.26
      2000 + int(parts[1]), 3 * int(substr(parts[0], 2)) - 2, 1)
    WHEN size(parts) = 2 THEN make_date(  -- monthly: Ene.2026
      int(parts[1]),
      element_at(map('ene',1,'feb',2,'mar',3,'abr',4,'may',5,'jun',6,'jul',7,'ago',8,
                     'sep',9,'set',9,'oct',10,'nov',11,'dic',12), lower(parts[0])),
      1)
    WHEN periodo_label RLIKE '^[0-9]{4}$' THEN make_date(int(periodo_label), 1, 1)  -- annual
  END AS fecha,
  -- "n.d." means not available yet.
  CASE WHEN raw_value = 'n.d.' THEN NULL ELSE try_cast(raw_value AS DOUBLE) END AS valor,
  fetched_at,
  source_file
FROM labeled;

CREATE OR REFRESH STREAMING TABLE silver.series_observaciones
COMMENT 'BCRP observations, latest value per (codigo, fecha)';

-- SCD type 1 upsert: re-ingesting overlapping ranges never duplicates rows,
-- and revised values replace older ones.
CREATE FLOW series_observaciones_cdc AS AUTO CDC INTO silver.series_observaciones
FROM STREAM(series_points)
KEYS (codigo, fecha)
SEQUENCE BY fetched_at
STORED AS SCD TYPE 1;
