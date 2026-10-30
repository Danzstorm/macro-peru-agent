-- Gold: what the agent's tools query.

CREATE OR REFRESH MATERIALIZED VIEW gold.series_catalogo
COMMENT 'Curated catalog of BCRP series available to the agent'
AS SELECT codigo, alias, nombre, frecuencia, unidad, descripcion
FROM read_files('/Volumes/${catalog}/raw/raw_api/catalog/', format => 'json');

CREATE OR REFRESH MATERIALIZED VIEW gold.series_observaciones (
  CONSTRAINT fecha_valida EXPECT (fecha IS NOT NULL),
  CONSTRAINT codigo_valido EXPECT (codigo IS NOT NULL),
  -- Sanity ranges per series (warn only): catch unit or parsing changes in the API.
  CONSTRAINT valor_en_rango EXPECT (
    valor IS NULL OR CASE alias
      WHEN 'tipo_cambio_venta' THEN valor BETWEEN 2 AND 6
      WHEN 'tasa_referencia' THEN valor BETWEEN 0 AND 15
      WHEN 'reservas_internacionales' THEN valor BETWEEN 30000 AND 200000
      WHEN 'precio_cobre' THEN valor BETWEEN 100 AND 2000
      ELSE valor BETWEEN -50 AND 50
    END
  )
)
COMMENT 'Observed values (not projections) of BCRP series'
AS SELECT codigo, alias, fecha, periodo_label, valor, fetched_at AS _ingested_at
FROM silver.series_observaciones;
