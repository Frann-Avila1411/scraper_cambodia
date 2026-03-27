# Web Scraping - Cambodia IP Trademark Search

Scraper asíncrono en Python para descargar detalles e imágenes de marcas registradas desde el portal de propiedad intelectual de Camboya.

## Objetivo

Para cada Filing Number configurado en el script, el proyecto genera:

- Un archivo HTML con el detalle de la marca.
- Un archivo JPG con el logo de la marca.

## Stack Tecnológico

- Browser automation: Playwright (async)
- HTTP requests: aiohttp
- Lenguaje: Python 3.10+
- Reintentos: tenacity

## Estructura del Proyecto

```text
scraper_cambodia/
├─ main.py
├─ scraper/
│  ├─ __init__.py
│  ├─ cli.py
│  ├─ config.py
│  ├─ network.py
│  ├─ rate_limiter.py
│  ├─ reporting.py
│  └─ workflow.py
├─ requirements.txt
├─ README.md
├─ MAPA_CODIGO.md
└─ output/
```

## Instalación

1. Clonar el repositorio

```bash
git clone https://github.com/Frann-Avila1411/scraper_cambodia.git
cd scraper_cambodia
```

2. Crear y activar entorno virtual

```bash
python -m venv venv
```

Windows (PowerShell):

```bash
venv\Scripts\Activate.ps1
```

Windows (CMD):

```bash
venv\Scripts\activate.bat
```

macOS/Linux:

```bash
source venv/bin/activate
```

3. Instalar dependencias

```bash
pip install -r requirements.txt
```

4. Instalar navegador de Playwright

```bash
python -m playwright install chromium
```

## Ejecución

```bash
python main.py
```

## Ejecución por Consola

El scraper acepta Filing Numbers por argumentos, sin editar el código.

### 1. Un solo número

```bash
python main.py KH/49633/12
```

### 2. Varios números

```bash
python main.py KH/49633/12 KH/59286/14 KH/83498/19
```

### 3. Desde archivo .txt

```bash
python main.py -f filing_numbers.txt
```

Ejemplo de archivo `filing_numbers.txt`:

```text
KH/49633/12
KH/59286/14
KH/83498/19
```

### Comportamiento por defecto

Si no se envía ningún número por consola, el scraper usa la lista base definida en el código.

## Configuración de Números Base

La lista base se define en `scraper/config.py` y funciona como fallback:

Ejemplo:

```python
DEFAULT_FILING_NUMBERS = [
    "KH/49633/12",
    "KH/59286/14",
    "KH/83498/19",
]
```

## Formato de Salida

Los archivos se guardan en la carpeta output usando el número sin /:

- KH4963312_1.html  -> detalle de marca
- KH4963312_2.jpg   -> imagen/logo de marca

## Comportamiento del Scraper

- Captura cookies de sesión al inicio con Playwright.
- Intenta búsqueda por API HTTP.
- Si la API no devuelve match exacto, usa fallback vía UI con Playwright para recuperar el id correcto.
- Guarda un HTML estático con los datos de detalle para garantizar que sea visible al abrirlo localmente.
- Descarga la imagen asociada a la marca.
- Aplica reintentos automáticos en fallos transitorios de red.

## Manejo de Errores

- Si no encuentra coincidencia exacta para un número, registra warning y guarda archivo debug de búsqueda.
- Si una marca no tiene logo, continúa con la siguiente sin interrumpir el proceso.
- Si hay límite de solicitudes o timeout, aplica reintentos y degradación controlada.

## Documentación Adicional

- MAPA_CODIGO.md: explicación simple de la función de cada archivo Python.


# Análisis Técnico del Proyecto

## 1. Contexto del Sitio

El portal Cambodia IP funciona como una SPA (Single Page Application). La UI realiza búsquedas de marcas mediante llamadas a endpoints internos, sin recargar la página completa.

Esto implica que:

- Hacer solo requests directos no siempre replica el comportamiento real de la interfaz.
- Para descargar detalle e imagen correctamente se requiere una sesión válida (cookies activas).

## 2. Documentación de Hallazgos

- Endpoint de búsqueda: La consulta de marcas se realiza con una petición POST a:
    https://digitalip.cambodiaip.gov.kh/api/v1/web/trademark-search
- Autenticación y cabeceras: La búsqueda requiere enviar datos en formato JSON (Content-Type: application/json), junto con el token de seguridad en la cabecera X-XSRF-TOKEN y las cookies de sesión laravel_session y XSRF-TOKEN.
- Estructura de la respuesta: El servidor devuelve un objeto JSON y los resultados útiles están dentro del arreglo data.data.
- Identificador interno: El sistema no usa el Filing Number (por ejemplo KH/49633/12) para las consultas de detalle, sino un id interno (por ejemplo KHT201249633). También devuelve el campo booleano logo para indicar si existe imagen asociada.
- Endpoint de imágenes: La imagen en alta resolución se descarga con GET a:
    https://digitalip.cambodiaip.gov.kh/trademark-detail-logo/{id}?type=ts_logo_detail_screen
- Protección de imágenes: Para descargar sin bloqueo es necesario inyectar cookies laravel_session y XSRF-TOKEN, además de replicar cabeceras clave como User-Agent y Referer.

## 3. Estrategia Técnica

Se observó que la búsqueda se realiza mediante POST a /api/v1/web/trademark-search. Esa respuesta devuelve un JSON del que se extrae un id interno (por ejemplo KHT201249633) y se verifica la existencia de imagen con la propiedad logo.

Luego se confirmó que la descarga en /trademark-detail-logo/{ID} requiere obligatoriamente cookies de sesión (laravel_session y XSRF-TOKEN), además de User-Agent y Referer.

Por lo tanto, la estrategia aplicada es:

1. Ejecutar Playwright en modo headless al inicio.
2. Navegar una sola vez al buscador para capturar cookies y token de sesión.
3. Cerrar el navegador para minimizar recursos.
4. Transferir esos valores a una sesión de cliente HTTP asíncrono puro (aiohttp).
5. Usar aiohttp para las peticiones POST de búsqueda y GET de descarga (imagen y HTML) de forma rápida y estable.

## 4. Estrategia de Resolución del ID Interno

Orden de resolución:

1. Búsqueda por API con match exacto por Filing Number normalizado.
2. Fallback por UI (Playwright) para capturar el resultado real de la interfaz.
3. Búsqueda paginada y validaciones adicionales cuando no hay match directo.
4. Si no se encuentra coincidencia, se genera archivo debug para análisis.

## 5. Generación de Archivos de Salida

Para cada número solicitado:

- Se guarda un HTML estático con campos de detalle (marca, owner, status, fechas, etc.).
- Se guarda la imagen/logo correspondiente.

Formato de nombres:

- output/KH4963312_1.html
- output/KH4963312_2.jpg

Esta salida asegura trazabilidad y visualización correcta incluso fuera del entorno web original.

## 6. Manejo de Errores

El scraper contempla:

- Reintentos en errores de red y timeouts.
- Continuidad del flujo si un número no se encuentra.
- Manejo de límites de solicitudes (rate limit) con degradación controlada.
- Registro de eventos con logs informativos.

## 7. Resultado Final

Con el desarrollo realizado, el scraper:

- Resuelve correctamente los Filing Number objetivo.
- Descarga la imagen correcta por marca.
- Genera HTML con contenido útil y legible (no vacío).
- Mantiene ejecución estable y asíncrona con bajo uso de recursos.

## 8. Limitaciones Conocidas

- En algunos periodos, la API de búsqueda puede devolver resultados genéricos y no aplicar el filtro exacto por Filing Number.
- Cuando eso ocurre, el scraper usa fallback por UI (Playwright) para resolver el id interno correcto.
- Si el sitio aplica límites temporales (429/403), el scraper espera y reintenta, lo que puede aumentar el tiempo total de ejecución.

## Tiempo Real Invertido en la Prueba

- Tiempo total estimado en desarrollo: 7 horas 30 minutos aprox.
- Este tiempo considera investigación, implementación, depuración, refactor y documentación de forma manual.

Desglose de las etapas de desarrollo:

- Investigación inicial del sitio y validación manual de endpoints
- Implementación base del scraper asíncrono (cookies, búsqueda y descarga)
- Depuración de coincidencia incorrecta de resultados y fallback por UI
- Corrección de salida HTML (contenido real y formato legible)
- Robustez anti-bloqueo (rate limit, pausas, manejo 429/403)
- Refactor modular + documentación final (README y mapa de código)