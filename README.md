# Proyecto Grupo 7

Proyecto de Adquisición y Tratamiento de Datos del Grado en Ciencia de Datos. Queremos desarrollar una página web que ayude a planificar viajes reuniendo transporte, alojamiento, meteorología, gastronomía, puntos de interés, mapas y una estimación de costes.

## Entregable 1

La [propuesta inicial del proyecto](entregable_1/propuesta_proyecto_grupo7.docx) contiene los integrantes, el objetivo, las fuentes de datos previstas y las fases de desarrollo. Se conserva el documento original sin modificar su contenido.

## Entregable 2

**En preparación.** Esta carpeta reúne el código y los datos disponibles para estudiar la viabilidad de las fuentes. La segunda entrega todavía no está terminada.

En [codigos](entregable_2/codigos/) están juntos los ocho archivos Python y el CSV, sin subcarpetas: Wikivoyage, Open-Meteo, mapas y rutas, KAYAK, Google Flights, Google Hotels, DiscoverCars y Booking a través de un proveedor de RapidAPI. El CSV de Wikivoyage contiene 102 registros de Roma.

Los scripts son pruebas independientes. La aplicación web todavía está pendiente y no se da por hecho que todas las fuentes funcionen o estén integradas. En esta revisión se hicieron comprobaciones locales, sin consultar los servicios externos.

## Organización

```text
entregable_1/
    propuesta_proyecto_grupo7.docx
entregable_2/
    codigos/
        booking_api_prueba.py
        discovercars_prueba.py
        google_flight_prueba.py
        google_hotels_prueba.py
        kayak_prueba.py
        open_meteo_prueba.py
        prueba_mapa_rutas.py
        wikivoyage.py
        datos_wikivoyage.csv
```

Las próximas entregas se añadirán en sus propias carpetas cuando haya archivos que incorporar.

## Ejecutar Wikivoyage

Desde la carpeta del repositorio, con Python instalado:

```powershell
python -m pip install requests beautifulsoup4
python entregable_2/codigos/wikivoyage.py
```

El script consulta Roma por defecto y necesita conexión a Internet. Guarda las nuevas extracciones en una subcarpeta `resultados_wikivoyage`, que no se sube a Git. El CSV adjunto se conserva como ejemplo y no se sobrescribe.

Los demás scripts también son ejemplos y contienen fechas y parámetros que deben revisarse antes de ejecutarlos. La prueba de Booking lee su clave desde la variable de entorno `RAPIDAPI_KEY`; no se incluye ninguna clave en el repositorio.
