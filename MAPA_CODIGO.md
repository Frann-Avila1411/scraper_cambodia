# Mapa Rapido del Codigo

Este documento resume de forma simple para que sirve cada archivo principal del proyecto.

## Vista General

El proyecto esta dividido en modulos para separar responsabilidades.

- main.py: punto de entrada que arranca todo.
- scraper/: carpeta con la logica principal.

## Archivos Python y su Funcion

### main.py

Es el archivo que se ejecuta. Hace tres cosas:

1. Configura logs.
2. Asegura que exista la carpeta output.
3. Lee los Filing Numbers por consola y ejecuta el scraper.

### scraper/config.py

Guarda configuraciones globales del proyecto:

- Rutas de carpetas.
- User-Agent.
- Cookies requeridas.
- Numeros por defecto.
- URLs del sitio.
- Parametros de control de velocidad.

### scraper/cli.py

Maneja la entrada por consola:

- Recibe uno o varios Filing Numbers.
- Permite usar archivo .txt con -f.
- Si no se envia nada, usa la lista por defecto.

### scraper/rate_limiter.py

Controla el ritmo de peticiones para reducir riesgo de bloqueo:

- Limita solicitudes por minuto.
- Mantiene un intervalo minimo entre peticiones.
- Aplica pequenas esperas aleatorias.

### scraper/network.py

Centraliza las peticiones HTTP:

- Usa el limitador de velocidad.
- Aplica reintentos automáticos ante errores de red.
- Si aparece 429 o 403, espera antes de continuar.
- Devuelve JSON o contenido binario segun el tipo de solicitud.

### scraper/reporting.py

Genera salidas del scraper:

- Construye el HTML final de detalle de marca.
- Guarda archivos debug cuando no hay coincidencias.
- Resume resultados para diagnostico.

### scraper/workflow.py

Contiene el flujo principal del proceso:

1. Obtiene cookies de sesion.
2. Busca la marca por API.
3. Si falla, intenta por UI con Playwright.
4. Si aun falla, prueba estrategias de respaldo.
5. Guarda HTML y descarga imagen.
6. Repite para cada Filing Number.

## Orden Real de Ejecucion

1. main.py
2. scraper/cli.py
3. scraper/workflow.py
4. scraper/network.py y scraper/rate_limiter.py
5. scraper/reporting.py

## Salidas Generadas

Los archivos se guardan en output:

- KHxxxxxxx_1.html: detalle de la marca.
- KHxxxxxxx_2.jpg: imagen de la marca.
- KHxxxxxxx_debug_search.json: ayuda de diagnostico cuando no hay match.
