# Proyecto Grupo 7

Proyecto de Adquisición y Tratamiento de Datos del Grado en Ciencia de Datos. Queremos desarrollar una página web que ayude a planificar viajes reuniendo transporte, alojamiento, meteorología, gastronomía, puntos de interés, mapas y una estimación de costes.

## Entregable 1

La [propuesta inicial del proyecto](entregable_1/propuesta_proyecto_grupo7.docx) contiene los integrantes, el objetivo, las fuentes de datos previstas y las fases de desarrollo. Se conserva el documento original sin modificar su contenido.

## Entregable 2

El [documento de la segunda entrega](entregable_2/entregable_2_grupo7.pdf) recoge las pruebas de acceso y extracción de datos realizadas por el grupo, los resultados, las limitaciones encontradas y la selección de fuentes para continuar el desarrollo. El PDF se conserva sin modificar su contenido y está directamente en `entregable_2`, junto a la carpeta `codigos`.

En [codigos](entregable_2/codigos/) están juntos los ocho archivos Python y el CSV, sin subcarpetas: Wikivoyage, Open-Meteo, mapas y rutas, KAYAK, Google Flights, Google Hotels, DiscoverCars y Booking a través de un proveedor de RapidAPI. El CSV de Wikivoyage contiene 102 registros de Roma.

Los scripts son pruebas independientes. La segunda entrega documenta los resultados obtenidos por el grupo; la integración de las fuentes y el desarrollo de la aplicación web siguen pendientes.

## Organización

```text
entregable_1/
    propuesta_proyecto_grupo7.docx
entregable_2/
    entregable_2_grupo7.pdf
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
