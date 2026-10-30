# macro-peru-agent

Analista Macro Perú: agente de IA en Azure Databricks que combina datos observados de la API BCRPData (tools sobre tablas gold) con RAG sobre Reportes de Inflación y Notas Informativas del BCRP.

Proyecto educativo con datos reales, preparado para el **Iquitos Data Fest**.

- Plan por fases: [`PLAN.md`](PLAN.md)
- Plan actualizado y hallazgos sobre las fuentes: [`docs/plan-actualizado.md`](docs/plan-actualizado.md)
- Contexto para Claude Code: [`CLAUDE.md`](CLAUDE.md)

## Entorno local

```bash
uv sync                      # runtime + dev
uv sync --extra agent        # + dependencias del agente (F7 en adelante)
uv run ruff check .
uv run pytest -m "not integration"
```
