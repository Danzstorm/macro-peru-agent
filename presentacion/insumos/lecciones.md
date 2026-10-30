# Lecciones aprendidas

Problemas encontrados durante el proyecto y cómo se resolvieron.

## 2026-10-30 — La API BCRPData está detrás de un filtro anti-bot

- **Síntoma:** la API devuelve status 200 con una página HTML ("Pardon Our Interruption") en lugar de JSON. Los PDFs del BCRP devuelven 403 desde la red local.
- **Causa:** Incapsula (Imperva) exige ejecutar un desafío en JavaScript. El sitio web con los PDFs (`www.bcrp.gob.pe`) usa un modo más estricto (ver la corrección).
- **Solución:** `BcrpClient` detecta el desafío, lo resuelve una vez con Chromium headless (Playwright) y reutiliza las cookies con `requests`. Funciona desde la red local y desde Azure.
- **Corrección (mismo día):** los PDFs tampoco salen desde Azure. El "200" era la página del desafío (6183 bytes). `www.bcrp.gob.pe` exige verificación interactiva (tipo CAPTCHA) incluso a un navegador headless; los PDFs se descargan a mano y se suben al Volume. Lección: validar el contenido (`%PDF`), no el status HTTP.
- **Detalle:** [`docs/plan-actualizado.md`](../../docs/plan-actualizado.md).

## 2026-10-30 — Trampas silenciosas de la API

- Pedir varias series en una llamada las reordena por código y descarta las de otra frecuencia, **sin error**. Solución: una serie por llamada.
- El encoding varía por serie (UTF-8 o Latin-1). Solución: decodificar como UTF-8 y, si falla, como Latin-1.
- "Sep" en series mensuales y "Set" en diarias. Solución: el parser acepta ambas.
- Un código inválido devuelve 200 con JSON roto. Solución: `BcrpError` explícito.
