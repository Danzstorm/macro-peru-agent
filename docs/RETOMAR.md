# Retomar el proyecto

> Snapshot del 2026-10-30. Lee esto antes de seguir; complementa a [`PLAN.md`](../PLAN.md) y [`plan-actualizado.md`](plan-actualizado.md).

## 1. Dónde quedamos

| Fase | Estado | Nota |
|---|---|---|
| F0 Repo y entorno | ✅ | `uv`, `ruff`, `pytest` (36 tests). Repo público `Danzstorm/macro-peru-agent`. |
| F1.1 API BCRP | ✅ | `BcrpClient` con bypass del filtro anti-bot (Playwright). 11 series en `config/series.yml`. |
| F1.2 PDFs | 🔄 | El sitio exige verificación humana: los PDFs se bajan a mano a `data/pdfs/`. Falta `config/documentos.yml`. |
| F2 Bootstrap Azure | ✅ | SP `sp-macro-peru-cicd` con OIDC. Subjects en formato inmutable (ver §4). |
| F3 Terraform | ✅ | Workspace `dbw-macro-peru-dev`, catálogo `macro_peru_dev`, volumes `raw_api` y `raw_docs`. |
| F4 Spike RAG | ⏳ | **Siguiente paso importante** (go/no-go). Depende de F1.2. |
| F5 Series | ✅ con 1 pendiente | Gold con 11 series desde 2015. El trigger automático no dispara (ver §3). |
| F6–F13 | ⏳ | Pipeline documental, UC Functions, agente, evaluación, serving + app, CI/CD, observabilidad, presentación. |

Último commit al cerrar: `6115624`.

## 2. Costos: qué existe y qué cobra

| Recurso | Cobra en reposo | Aprox. |
|---|---|---|
| **NAT Gateway + IP pública** (`rg-macro-peru-dev-managed`, creados por el workspace) | **Sí, por hora** | **~USD 35/mes**. Es el costo fijo principal. |
| Storage accounts (UC, managed, tfstate) | Sí, por GB | Centavos. |
| Workspace Databricks | No (solo por uso) | 0 en reposo. |
| SQL Warehouse `Serverless Starter Warehouse` | Solo encendido | Se apaga solo. Estaba `STOPPED`. |
| Pipeline `series`, job `refresh_series` | Solo al correr | Serverless, segundos por corrida. |
| Vector Search, Model Serving, Apps | — | **No creados todavía.** Cobran por hora cuando existan: crearlos solo al trabajar y borrarlos al terminar. |
| GitHub Actions `ingest-series` (diario 08:00 Lima) | Gratis (repo público) | Sube ~11 archivos/día al Volume. |

Hay budget con alertas al 50/80/100% sobre `rg-macro-peru-dev` y el RG administrado.

### Opción 1: pausa corta (días) — mantener todo

No hacer nada más. Costo ~USD 1/día por el NAT Gateway. Opcional: `gh workflow disable ingest-series.yml`.

### Opción 2: pausa larga (semanas) — costo casi cero

El NAT Gateway no se puede borrar por separado (el RG administrado está bloqueado); se va solo destruyendo el workspace.

```bash
gh workflow disable ingest-series.yml

cd infra/terraform
export TF_VAR_alert_emails='["<tu-email>"]'
terraform plan -destroy -var-file=envs/dev.tfvars   # revisar
terraform destroy -var-file=envs/dev.tfvars
```

- Se pierden el workspace, el catálogo y los datos. **No importa:** todo se reconstruye desde código y la API.
- `infra/bootstrap` (tfstate + SP de OIDC) **no se destruye**: cuesta centavos y evita repetir F2.
- El metastore de Unity Catalog es de la cuenta y la región; no se toca.

### Volver después de la opción 2

```bash
az login
cd infra/terraform
terraform init -backend-config="storage_account_name=stmacroperutfpast38"
terraform apply -var-file=envs/dev.tfvars
# El host del workspace cambia:
databricks auth login --host <nuevo workspace_url> --profile macro-dev
gh variable set DATABRICKS_HOST --body "<nuevo workspace_url>"
# actualizar workspace.host en databricks.yml
cd ../.. && databricks bundle deploy -t dev --profile macro-dev
gh workflow enable ingest-series.yml
gh workflow run ingest-series.yml -f mode=full
databricks bundle run series -t dev --profile macro-dev
```

## 3. Pendiente abierto de F5: el trigger por llegada de archivos

**Síntoma:** el workflow sube archivos al Volume, pero el job `refresh_series` (trigger `file_arrival`) nunca arranca.

**Causa:** la external location `el-macro-peru-dev` tiene *file events* en modo automático. Databricks debe crear una suscripción de Event Grid y una Storage Queue sobre `stmacroperudevpswd5d`, y no lo logra.

**Ya probado:** se agregaron al Access Connector `Storage Queue Data Contributor`, `Storage Account Contributor` (storage) y `EventGrid Data Contributor` (RG), y se reactivaron los file events desde la CLI. Siguió sin crearse.

**Hipótesis no verificada:** `EventGrid Data Contributor` solo permite publicar eventos; crear suscripciones necesita `EventGrid EventSubscription Contributor`. El storage tiene `allowSharedKeyAccess = false`, que también podría influir.

**Opciones:**
- **A (recomendada):** desactivar file events en esa external location (`enable_file_events = false` en `databricks_external_location.uc_root`). El trigger pasa a listar la carpeta cada minuto. Límite: 10.000 archivos en `raw_api/series/` (~2,5 años a 11 por día).
- **B:** agregar `EventGrid EventSubscription Contributor` sobre el RG y reactivar file events. Más permisos, sin garantía.

Mientras tanto, el pipeline se corre a mano: `databricks bundle run series -t dev --profile macro-dev`.

Nota para F11: el SP de CI/CD solo puede asignar `Storage Blob Data Contributor` (condición en `infra/bootstrap`). Si CI debe crear la infra desde cero, ampliar esa condición o crear esos roles localmente.

## 4. Trampas ya resueltas (no repetir)

- **API BCRP detrás de un WAF anti-bot:** responde 200 con HTML. El cliente lo resuelve con Playwright. La ingesta corre en GitHub Actions porque serverless no tiene las librerías de Chromium.
- **La API reordena series** cuando se piden varias juntas: se pide una serie por llamada.
- **Septiembre es `Sep` en mensuales y `Set` en diarias.** El parser de silver acepta ambas.
- **OIDC de GitHub con subjects inmutables:** el `sub` es `repo:Danzstorm@54243238/macro-peru-agent@1440036337:...`. Ver con `gh api repos/Danzstorm/macro-peru-agent/actions/oidc/customization/sub`.
- **`terraform plan` en `infra/terraform` pide `alert_emails`:** pasarlo con `TF_VAR_alert_emails`, nunca en el repo.

## 5. Próximos pasos, en orden

1. **Decidir §3** (A o B) y cerrar F5.
2. **F1.2:** bajar a mano 2 Reportes de Inflación (marzo y junio 2026) y ~12 Notas Informativas a `data/pdfs/`; armar `config/documentos.yml` con fechas reales; `scripts/validate_manifest.py` (firma `%PDF`, páginas, sha256).
3. **F4 spike:** subir PDFs a `raw_docs`, `ai_parse_document`, comparar chunking, medir recall@5. ⚠️ El endpoint de Vector Search cobra por hora: crearlo al empezar y borrarlo al terminar la sesión.
4. F6 a F13 según `PLAN.md`.

## 6. Datos útiles

| Qué | Valor |
|---|---|
| Perfil CLI | `macro-dev` |
| Workspace | `https://adb-7405618273251585.5.azuredatabricks.net` |
| Suscripción | `2bf29b75-ddc1-40de-94c5-59f988784057` |
| Storage tfstate | `stmacroperutfpast38` (RG `rg-macro-peru-tfstate`) |
| SQL Warehouse | `b4ec8f117c8b4716` |
| Job `refresh_series` | `691488820521214` |
| Pipeline `series` | `769e1c84-cb8c-4c34-aa55-5b6f0a3bf2cd` |
| LLM / embeddings | `databricks-claude-sonnet-5-5` / `databricks-qwen3-embedding-0-6b` |
