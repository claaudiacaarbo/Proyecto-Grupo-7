# My Travel Plan · Grupo 7

Proyecto de Adquisición y Transmisión de Datos del Grado en Ciencia de Datos. Queremos desarrollar una página web que ayude a planificar viajes reuniendo transporte, alojamiento, meteorología, gastronomía, puntos de interés, mapas y una estimación de costes.

## Entregable 1

La [propuesta inicial del proyecto](entregable_1/propuesta_proyecto_grupo7.docx) contiene los integrantes, el objetivo, las fuentes de datos previstas y las fases de desarrollo. Se conserva el documento original sin modificar su contenido.

## Entregable 2

El [documento de la segunda entrega](entregable_2/entregable_2_grupo7.pdf) recoge las pruebas de acceso y extracción de datos realizadas por el grupo, los resultados, las limitaciones encontradas y la selección de fuentes para continuar el desarrollo. El PDF se conserva sin modificar su contenido y está directamente en `entregable_2`, junto a la carpeta `codigos`.

En [codigos](entregable_2/codigos/) están juntos los ocho archivos Python y el CSV, sin subcarpetas: Wikivoyage, Open-Meteo, mapas y rutas, KAYAK, Google Flights, Google Hotels, DiscoverCars y Booking a través de un proveedor de RapidAPI. El CSV de Wikivoyage contiene 102 registros de Roma.

Los scripts de esta entrega se ejecutan de forma independiente y sirvieron para seleccionar las fuentes del planificador integrado.

## Entregable 3

El [informe de la tercera entrega](entregable_3/Entregable3_Grupo7.pdf) documenta el diseño de las funciones y muestra un ejemplo de ejecución del [My Travel Plan](entregable_3/My%20Travel%20Plan/). El programa se ejecuta en la terminal y reúne vuelos, alojamiento, alquiler de coches, meteorología y recomendaciones de visitas y gastronomía. También muestra una estimación de los costes disponibles y guarda la ruta a pie en un mapa interactivo (`mapa_ruta.html`). La aplicación web sigue siendo el objetivo del proyecto.

### Cómo ejecutar el planificador

Se necesita Python 3.11 o superior, Microsoft Edge y conexión a internet. Abre la carpeta `entregable_3/My Travel Plan` en tu copia del repositorio.

- **Windows.** Haz doble clic en `iniciar_planificador.bat`.
- **macOS y Linux.** Abre una terminal en esa carpeta y ejecuta `python3 -X utf8 programa/iniciar.py`.

El lanzador instala las dependencias la primera vez. Sigue las preguntas de la terminal y, cuando aparezca la ubicación de `mapa_ruta.html`, abre ese archivo con el navegador. Los filtros y los formatos de entrada se explican en las [instrucciones de uso](entregable_3/My%20Travel%20Plan/INSTRUCCIONES.txt).

## Organización

```text
entregable_1/
    propuesta_proyecto_grupo7.docx
entregable_2/
    entregable_2_grupo7.pdf
    README.md
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
entregable_3/
    Entregable3_Grupo7.pdf
    My Travel Plan/
        iniciar_planificador.bat
        INSTRUCCIONES.txt
        programa/
            iniciar.py
            planificador.py
            requirements.txt
            modulos/
                reservas.py
                tiempo.py
                rutas.py
                wikivoyage.py
```

Las próximas entregas se añadirán en sus propias carpetas cuando haya archivos que incorporar.
