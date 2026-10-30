# CLAUDE.md — macro-peru-agent

## Qué es este proyecto
Agente de IA "Analista Macro Perú" en **Azure Databricks**. Combina:
- **Datos observados** de la API pública BCRPData (tipo de cambio, inflación, tasa de referencia, PBI) → medallion → UC Functions como tools.
- **RAG** sobre PDFs del BCRP (Reportes de Inflación y Notas Informativas del Programa Monetario) → `ai_parse_document` → chunks → Vector Search.
- Agente LangGraph envuelto en MLflow `ResponsesAgent`, evaluado con MLflow 3, servido en Model Serving con una Databricks App como UI.
- Infraestructura con **Terraform**, recursos de Databricks con **Declarative Automation Bundles** (ex Databricks Asset Bundles) y CI/CD con **GitHub Actions + OIDC**.

El plan maestro está en `PLAN.md`. **Trabaja siempre por fases** y respeta los criterios de aceptación de cada una.

## Cómo trabajar
1. Antes de escribir código en una fase, resume qué archivos vas a crear o modificar y espera confirmación si la fase toca infraestructura o costos.
2. Al terminar una fase: corre los checks (`ruff`, `pytest`, `terraform validate`, `databricks bundle validate`), marca las casillas en `PLAN.md` y propón un mensaje de commit.
3. Los puntos marcados ⚠️ VERIFICAR en `PLAN.md` **no se asumen**: confírmalos con la documentación oficial, `databricks bundle schema`, `--help` de la CLI o una llamada real. Si algo difiere del plan, actualiza `PLAN.md` y avísame.
4. Si algo falla dos veces seguidas por la misma causa, detente y explícame el problema con opciones, en lugar de seguir probando variantes.

## Comandos frecuentes
```bash
uv sync                                   # dependencias
uv run ruff check . && uv run pytest -m "not integration"
cd infra/terraform && terraform fmt -check && terraform validate
terraform plan -var-file=envs/dev.tfvars -out=tfplan
databricks bundle validate -t dev --profile macro-dev
databricks bundle deploy -t dev --profile macro-dev
databricks bundle run <recurso> -t dev --profile macro-dev
databricks bundle schema                   # verificar claves de recursos del bundle
```

## Reglas que NO se rompen
- **Nunca** ejecutes `terraform apply`, `terraform destroy`, `databricks bundle destroy` ni `databricks bundle deploy -t prod` sin mi confirmación explícita en el chat.
- **Avísame antes** de crear recursos que cobran mientras existen: endpoint de Vector Search, Databricks App y serving endpoints.
- **Cero secretos** en el repo: nada de client secrets, tokens ni `.tfvars` con datos sensibles. La autenticación de CI/CD es solo OIDC.
- **No inventes datos económicos.** Las cifras en `evals/` y en ejemplos salen de la API o de los PDFs reales. Si no las verificaste, déjalas como `(completar)`.
- No hardcodees catálogos ni endpoints: usa las variables del bundle (`${var.catalog}`, `${var.llm_endpoint}`, `${var.embedding_endpoint}`, `${var.vs_endpoint}`).
- Respeta la regla de oro del agente: **observado → tools (API); proyección o explicación → RAG (documentos); si discrepan, mostrar ambos con fecha.**

## Convenciones
- Idioma: documentación, comentarios de cara al usuario, prompts y textos de la app en **español neutro** (tú, tienes, puedes). Identificadores de código en inglés; nombres de tablas y columnas del dominio en español (`series_observaciones`, `fecha_publicacion`).
- Python 3.11+, gestionado con `uv`. Estilo con `ruff`. Type hints en el código de `src/`.
- Pipelines: Lakeflow Spark Declarative Pipelines (SQL para bronze/gold, Python cuando haya lógica de parsing). Serverless siempre que se pueda.
- Unity Catalog: catálogo `macro_peru_dev` (dev) / `macro_peru` (prod); schemas `raw`, `bronze`, `silver`, `gold`, `agents`.
- `gold.doc_chunks` es una tabla Delta normal con **Change Data Feed habilitado** (requisito del índice Delta Sync), escrita con `MERGE`.
- Tags en todos los recursos del bundle: `project = macro-peru`, `env = ${bundle.target}`.
- Tests: unitarios sin red con fixtures en `tests/fixtures/`; los que tocan el workspace se marcan `@pytest.mark.integration`.
- Meses del BCRP en español abreviado, con **"Set"** para septiembre; valores `"n.d."` → NULL.

## Contexto del autor
Daniel Santos (@danielsantos.ai), Senior Data & AI Engineer. El proyecto es un caso educativo con datos reales para una presentación. Prioriza que cada pieza sea explicable: nombres claros, README por carpeta cuando ayude, y anota en `presentacion/insumos/lecciones.md` los problemas que encontremos y cómo los resolvimos.
