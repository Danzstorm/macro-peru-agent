# Paso a paso: construir un agente de IA con datos reales en Databricks

> **Para Claude (chat):** este documento es el guion técnico de mi charla en el **Iquitos Data Fest**. Complementa a `brief-para-claude.md` (contexto, mensajes clave y narrativa). Úsalo para armar las slides del recorrido técnico: **una slide (o dos) por paso**, cada una con (1) el concepto en una frase simple, (2) qué hicimos, (3) el comando o fragmento de código más representativo y (4) qué aprendimos. El público son estudiantes y profesionales con niveles distintos: explica cada término la primera vez que aparece. Los pasos marcados ⏳ todavía no están hechos: preséntalos como "lo que viene" y no inventes resultados; usa `[DATO PENDIENTE]`.

**Repositorio:** https://github.com/Danzstorm/macro-peru-agent: todo lo que aparece aquí está en el repo y se puede replicar.

---

## Mapa del recorrido

```
 1. Preparar el proyecto            ✅
 2. Conocer los datos reales        ✅ (API)  🔄 (PDFs)
 3. Llaves de la casa (identidad)   ✅
 4. Construir la casa (infra)       ✅
 5. ¿Funciona el RAG? (spike)       ⏳
 6. Datos que se actualizan solos   ⏳
 7. Documentos buscables            ⏳
 8. Herramientas del agente         ⏳
 9. El agente                       ⏳
10. El examen (evaluación)          ⏳
11. Publicarlo                      ⏳
12. Automatizar todo (CI/CD)        ⏳
13. Cuidar el bolsillo              ⏳
```

Analogía para toda la charla: **construir una casa**. Primero conocer el terreno (datos), luego las llaves y los cimientos (identidad e infraestructura), después las habitaciones (pipelines y agente), la inspección (evaluación) y, al final, abrir las puertas (despliegue).

---

## Paso 1 — Preparar el proyecto ✅

**Concepto:** un proyecto reproducible empieza con dependencias fijadas y tests, no con código suelto en un notebook.

**Qué hicimos**
- Repositorio Git con estructura por responsabilidades: ingesta, pipelines, tools, agente y evaluación.
- `uv` para gestionar Python (versión fijada: 3.12) y `pyproject.toml` con las dependencias.
- `ruff` (estilo) y `pytest` (tests) desde el día 1.

**Comando representativo**
```bash
uv sync && uv run ruff check . && uv run pytest
```

**Aprendizaje:** Python 3.13 instalado localmente no coincidía con lo que soporta Databricks; `uv` descarga la versión correcta sin tocar el sistema.

---

## Paso 2 — Conocer los datos reales antes de diseñar ✅🔄

**Concepto:** nunca diseñes un pipeline sobre lo que *dice* la documentación. Primero mira los datos reales.

**Fuentes**
- **API BCRPData:** series económicas (tipo de cambio, inflación, tasa de referencia, PBI, cobre). Pública y sin API key.
- **PDFs del BCRP:** Reportes de Inflación (trimestrales, ~190 páginas) y Notas Informativas del Programa Monetario (mensuales).

**Qué encontramos (la parte más interesante de la charla)**

1. **La API devuelve "200 OK" pero no entrega datos.** Está detrás de un firewall anti-bot (Incapsula) que responde a los programas con una página HTML: *"Pardon Our Interruption"*.
   - Probamos `curl`, `requests`, otros User-Agent y HTTP/1.1: todos bloqueados.
   - **Solución:** un navegador invisible (Chromium + Playwright) resuelve el desafío una sola vez; luego reutilizamos sus cookies con `requests`.
2. **El sitio de los PDFs pide verificación humana (tipo CAPTCHA).** Decisión ética: **no se automatiza**. Un script abre una ventana visible, la persona resuelve la verificación y el script descarga el resto. *Humano en el circuito* (human-in-the-loop).
3. **Trampas silenciosas de la API**, todas cubiertas con tests:

| Trampa | Consecuencia si no la ves |
|---|---|
| Pide 3 series juntas y la API **las reordena** | El agente muestra el PBI como si fuera la inflación |
| Mezcla frecuencias y **descarta series sin avisar** | Datos que desaparecen |
| Encoding distinto por serie | "Pol�tica Monetaria" |
| "Sep" en series mensuales, "Set" en diarias | Fechas que no se pueden leer |
| Código inválido → 200 con JSON roto | Errores lejos de la causa |

4. **Me equivoqué una vez:** una prueba "pasó" con status 200, pero eran 6183 bytes de la página del desafío, no un PDF. **Lección: valida el contenido (`%PDF`), no el status.**

**Fragmento representativo** (`src/macro_peru/bcrp/client.py`)
```python
body = self._get(url)
if is_challenge(body):                      # HTML instead of JSON
    cookies, user_agent = self.solver(url)  # headless Chromium, once
    self.session.cookies.update(cookies)
    self.session.headers["User-Agent"] = user_agent
    body = self._get(url)                   # retry with the browser's cookies
```

**Resultado:** 11 series verificadas contra la API real, 36 tests sin red con respuestas reales grabadas (*fixtures*).

---

## Paso 3 — Las llaves de la casa: identidad sin secretos ✅

**Concepto:** el robot que despliega (GitHub Actions) necesita permisos en Azure. La forma insegura es guardar una contraseña en GitHub. La forma correcta es **OIDC**: GitHub demuestra quién es con un token temporal y Azure confía en él solo para *este* repositorio.

**Qué hicimos** (Terraform en `infra/bootstrap/`, se ejecuta una sola vez)
- Storage para el **estado de Terraform**, con autenticación de Entra ID solamente (sin llaves de acceso) y con versionado.
- Una identidad (*service principal*) para CI/CD con **credenciales federadas**: solo la rama `main`, los pull requests y el environment `prod` de este repo pueden usarla.
- **Mínimo privilegio:** la identidad puede asignar permisos, pero **solo un rol específico** (lectura y escritura de storage), gracias a una *condición* en la asignación de rol.
- Environment `prod` en GitHub con aprobación manual, limitado a tags `v*`.

**Fragmento representativo**
```hcl
subject = "repo:Danzstorm/macro-peru-agent:ref:refs/heads/main"
issuer  = "https://token.actions.githubusercontent.com"
```

**Resultado:** cero secretos creados. En GitHub solo hay *variables* públicas (IDs).

**Aprendizaje:** el problema del huevo y la gallina. CI/CD necesita identidad y estado para correr Terraform, pero algo tiene que crearlos primero. Por eso existe un bootstrap local, una única vez.

---

## Paso 4 — Construir la casa: infraestructura como código ✅

**Concepto:** toda la infraestructura se declara en archivos versionados. Si la borras, la recreas con un comando.

**Qué hicimos** (`infra/terraform/`)
- Workspace de **Azure Databricks Premium** (East US 2) con compute **serverless** (no administras servidores).
- **Data lake** (ADLS Gen2) y un *Access Connector*: una identidad administrada con la que Databricks lee y escribe el lake sin contraseñas.
- **Unity Catalog** (el sistema de gobierno de datos): catálogo `macro_peru_dev` con schemas `raw → bronze → silver → gold` (arquitectura *medallion*) y `agents`, volumes para archivos crudos y permisos.
- **Presupuestos con alertas** al 50%, 80% y 100% desde el día 1.

**Comando representativo**
```bash
terraform plan -var-file=envs/dev.tfvars -out=tfplan
terraform apply tfplan
```

**Resultado:** 22 recursos creados. Un segundo `terraform plan` no muestra cambios (*idempotencia*). Modelos disponibles en el workspace: LLMs Claude y GPT, y el embedding multilingüe `qwen3-embedding`.

**Aprendizaje:** el provider de Databricks necesita que el workspace exista antes de configurarse. Se aplica en dos etapas: primero Azure con `-target` y luego Unity Catalog.

---

## Paso 5 — ¿Funciona el RAG con estos PDFs? (spike go/no-go) ⏳

**Concepto:** **RAG** (*Retrieval-Augmented Generation*) = antes de responder, el modelo busca los fragmentos relevantes de los documentos y responde solo con eso. Un *spike* es un experimento corto para decidir si seguir o cambiar de rumbo **antes** de construir todo.

**Qué haremos**
1. Leer los PDFs con `ai_parse_document`, que entiende títulos, secciones y tablas.
2. Cortarlos en fragmentos (*chunks*) con dos estrategias: por sección vs. tamaño fijo.
3. Agregar a cada chunk un prefijo con su contexto: `[Reporte de Inflación marzo 2026 | Sección: Inflación | pp. 45-46]`.
4. Indexarlos en **Vector Search** (búsqueda por significado) y comparar la búsqueda semántica con la híbrida (significado + palabras exactas).
5. Medir **recall@5**: ¿el fragmento correcto aparece entre los 5 primeros resultados?

**Criterio de éxito:** recall@5 ≥ 0.80 y **cero mezclas** entre reportes de fechas distintas cuando se filtra por fecha.

**Resultado:** [DATO PENDIENTE: matriz de experimentos E1–E4].

---

## Paso 6 — Datos que se actualizan solos ⏳

**Concepto:** arquitectura **medallion**: *bronze* (crudo, tal cual llegó) → *silver* (limpio y sin duplicados) → *gold* (listo para consumir).

**Qué haremos**
- Un job diario a las 08:00 (hora de Lima) que llama a la API y guarda el JSON crudo en un volume.
- Un pipeline declarativo (**Lakeflow**) que transforma bronze → silver → gold, con reglas de calidad (*expectations*): por ejemplo, ninguna fecha nula.
- Volver a correr el job **no duplica filas**.

**Por verificar:** si Chromium corre en serverless. Si no corre, el plan B es que GitHub Actions haga la ingesta.

---

## Paso 7 — Documentos buscables ⏳

Lo mismo que el paso 6, pero para PDFs: subirlos al volume → parsearlos (solo los nuevos, para no pagar dos veces) → chunks en una tabla Delta con *Change Data Feed* → el índice vectorial se sincroniza solo.

---

## Paso 8 — Las herramientas del agente ⏳

**Concepto:** el agente no "recuerda" números: **los consulta**. Cada herramienta es una función SQL gobernada en Unity Catalog.

| Herramienta | Para qué |
|---|---|
| `list_series()` | Qué series hay disponibles |
| `get_series(alias, desde, hasta)` | Datos observados reales |
| `compare_periods(...)` | Comparar promedios entre dos periodos |
| `list_reports(tipo)` | Saber cuál es "el último reporte" |
| `search_bcrp_reports(pregunta, fechas)` | Buscar en los PDFs con filtro de fecha |

---

## Paso 9 — El agente ⏳

**Concepto:** un agente = un LLM + herramientas + un ciclo "pienso → uso una herramienta → observo → respondo".

**Qué haremos:** LangGraph + MLflow `ResponsesAgent`, con un *system prompt* con reglas claras:
1. ¿Dato observado? → herramientas SQL.
2. ¿Proyección o explicación? → búsqueda en documentos.
3. ¿"El último"? → primero `list_reports` y después búsqueda con filtro de fecha.
4. Siempre citar la fuente con su fecha.
5. Si está fuera de alcance, decirlo y no inventar.

Cada respuesta deja un **trace** en MLflow: se ve qué herramientas usó y con qué datos.

---

## Paso 10 — El examen: evaluación automática ⏳

**Concepto:** *"Un agente sin evaluación es un demo, no un producto."*

**Qué haremos:** un set de ~60 preguntas con respuestas esperadas, sacadas de los documentos reales, y jueces automáticos (MLflow 3) que miden si citó la fuente, si se basó en lo recuperado, si usó la herramienta correcta y si evitó mezclar reportes. Si una métrica baja del umbral, **el despliegue se bloquea**.

**Resultado:** [DATO PENDIENTE].

---

## Paso 11 — Publicarlo ⏳

- **Model Serving:** el agente como endpoint, con *scale-to-zero* (no cobra si nadie lo usa).
- **Databricks App:** un chat con las fuentes citadas en un panel lateral.

---

## Paso 12 — Automatizar todo: CI/CD ⏳

- Cada pull request: lint, tests, `terraform plan` y validación del bundle.
- Cada merge a `main`: desplegar en dev y **correr la evaluación como gate**.
- **Demo estrella:** un PR que quita una regla del prompt y el pipeline **lo bloquea** porque la calidad baja.

---

## Paso 13 — Cuidar el bolsillo ⏳

- Qué cobra aunque no lo uses: el endpoint de Vector Search y la app encendida.
- Scripts `pause.sh` / `resume.sh` y `teardown.sh`.
- Costo real del proyecto según las tablas de billing: [DATO PENDIENTE].

---

## Errores reales y cómo se resolvieron (material para una slide)

| Problema | Causa | Solución |
|---|---|---|
| La API devuelve HTML con status 200 | Firewall anti-bot | Navegador headless una vez + cookies |
| Los PDFs piden verificación humana | Protección más estricta en el sitio web | Humano en el circuito, sin evadir la verificación |
| Una "descarga exitosa" no era un PDF | Confiar en el status HTTP | Validar la firma `%PDF` |
| Series mezcladas al pedirlas juntas | La API reordena sin avisar | Una serie por llamada |
| `networkidle` nunca termina | El sitio hace requests continuos | Esperar el evento `load` |
| Terraform no puede configurar Databricks | El workspace aún no existe | Aplicar en dos etapas (`-target`) |
| Rutas `/Workspace/...` rotas en Windows | Git Bash convierte las rutas | `MSYS_NO_PATHCONV=1` |
