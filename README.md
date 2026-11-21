# AgroCrédito · Evaluación agroclimática de predios para crédito agrícola

> Caso de estudio. Es un MVP construido por **AXA Climate** para **Agrapp**, una fintech de crédito agrícola en Colombia, dentro del proyecto **CGAP Colombia** (nov-2025 a jul-2026).
> Este repositorio conserva el código entregado, adaptado para que funcione en **modo demo** sin datos de clientes.

## El problema

Un crédito agrícola depende del predio: dónde está, si produce y qué riesgo climático tiene.
La validación era manual y no usaba datos climáticos. El proyecto buscó responder una pregunta:
**¿con solo unas coordenadas se puede evaluar un predio antes de desembolsar y monitorearlo después?**

## Qué hace la app

| Pestaña | Qué resuelve |
|---|---|
| **Inicio** | Identifica el predio a partir de un punto, un polígono dibujado o un GeoJSON. |
| **Validación Pre-Crédito** | Revisa la frontera agrícola, la aptitud del cultivo (UPRA), la altitud frente al cultivo, la actividad productiva (NDVI con Sentinel-2), la infraestructura (OSM/OSRM) y el riesgo climático (ERA5). Consolida todo en un semáforo y un score explicable. |
| **Monitoreo & Forecast** | Sigue un portafolio después del desembolso: NDVI reciente, clima de 14 a 30 días y pronóstico. |
| **Metodología** | Documenta cada indicador y sus umbrales. |

Exporta reportes en PDF para el comité de crédito.

## Mi rol

<!-- TODO David: confirmar o ajustar esta sección antes de hacer público el repo. -->

- Contraparte de Agrapp en el proyecto con AXA Climate y CGAP.
- Entregué los datos operativos: loan tape, reportes de portafolio y metodología de crédito y SARLAFT.
- Revisé los entregables y prioricé la retroalimentación de la app (jun-2026).
- Llevé el resultado al proceso de crédito: qué indicadores entran a la decisión y cuáles quedan solo para monitoreo.

## Lo que aprendimos

- **Unas coordenadas bastan para la inteligencia del predio.** Siete indicadores salen de fuentes públicas y casi todas no piden clave.
- **No todos los indicadores discriminan.** Algunos se activan en casi todos los créditos, por ejemplo en café, y pierden poder predictivo. Por eso el score se diseñó **con reglas, explicable y auditable**, no como un modelo estadístico.
- **El valor que se transfiere es el proceso**, más que el modelo: datos, flujo de validación y marco de monitoreo post-desembolso.

## Cómo correrla

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

- **Sin configuración** corre en modo demo: el catastro y las construcciones son de ejemplo. El clima, la altitud y la infraestructura se consultan en vivo.
- **NDVI** necesita una cuenta de servicio de Google Earth Engine. Copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` y llena la sección `[gee]`.
- **Base de datos real (opcional):** define `DATABASE_URL` con una base PostGIS. La base catastral original no se incluye en este repositorio.

La guía completa de despliegue está en [`deploy_guide.md`](deploy_guide.md).

## Estructura

```
app.py                  # Aplicación principal (4 pestañas)
utils/                  # Módulos de cálculo (NDVI, terreno, clima, riesgo, PDF)
datos/indicadores/      # Tablas de referencia (matriz de vulnerabilidad, altitudes)
.streamlit/             # Plantilla de credenciales
deploy_guide.md         # Guía de despliegue
```

## Fuentes de datos

- Sentinel-2 (NDVI) vía Google Earth Engine
- DEM SRTM vía AWS Terrain Tiles (sin clave)
- Clima ERA5 vía Open-Meteo (sin clave)
- OSM / OSRM para infraestructura (sin clave)
- UPRA / datos.gov.co para aptitud de cultivo (sin clave)

## Créditos y alcance

- **Desarrollo de la aplicación y la metodología:** AXA Climate.
- **Cliente y datos operativos:** Agrapp.
- **Marco del proyecto:** CGAP Colombia.
- **Cambios en este repositorio:** modo demo automático cuando no hay base de datos, y tolerancia a caídas de los servidores públicos de OpenStreetMap.

Es un MVP con fines demostrativos. No es una herramienta de decisión crediticia en producción. Ver la descarga de responsabilidad dentro de la app.
