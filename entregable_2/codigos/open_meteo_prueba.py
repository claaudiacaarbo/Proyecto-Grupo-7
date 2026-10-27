# Entregar la demostracion de que lo que se ha propuesto en la primera se puede hacer

import requests

"""
Vamos a comprobar que la API responde con el siguiente ejemplo:
Roma del 20 de octubre al 24 de octubre
Información que se va a devolver:

  - Temperatura máxima
  - Temperatura mínima
  - Precipitaciones
"""

# 1. Comprobar que la API responde. Lo probamos con las coordenadas de ROMA

url = "https://api.open-meteo.com/v1/forecast"

parametros = {"latitude": 41.89,
              "longitude": 12.49,
              "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum", # Los parámetros que querremos saber en un futuro
              "timezone": "auto"}  # Las fechas salen en la hora local del lugar

r = requests.get(url, params = parametros)

print(f"Código de estado: {r.status_code}")
print(r.json())

# 2. Convertir el nombre de una ciudad y su país en coordenadas
 
ciudad = "Roma"   # En la aplicación final la ciudad y el país los introducirá el usuario
pais = "Italia"
 
url_2 = "https://geocoding-api.open-meteo.com/v1/search"
parametros_2 = {"name": ciudad, "count": 10, "language": "es"} # Hay ciudades con el mismo nombre en distintos países, así que pedimos 10 resultados y luego elegimos el del país del usuario. Con "language": "es" el país viene escrito en español (Italia)
 
g = requests.get(url_2, params = parametros_2).json()
 
# g["results"] es una lista de lugares encontrados. Cada uno es un diccionario con latitude, longitude, name, country, country_code, etc.
lugar = None
for resultado in g["results"]:
    if resultado["country"].lower() == pais.lower():  # Comparamos el país del resultado con el que ha escrito el usuario (en minúsculas para que "Italia" e "italia" valgan igual)
        lugar = resultado
        break  # Nos quedamos con el primero que coincida, que es el más relevante
 
lat = lugar["latitude"] # sacamos el valor de la latitud del diccionario lugar creado arriba
lon = lugar["longitude"]
print(lugar["name"], lugar["country"], lat, lon)

# 3. Pedir el tiempo para las fechas del viaje

r = requests.get(
    "https://api.open-meteo.com/v1/forecast",
    params={
        "latitude": lat,  # Variable definida en el paso 2
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "start_date": "2026-10-20",  # Tienen que ir en el formato AAAA-MM-DD
        "end_date": "2026-10-24",
        "timezone": "auto"
    }
)

datos = r.json()["daily"]  # Recoge solo los datos de "daily" del diccionario

for i, dia in enumerate(datos["time"]):
    print(dia,
          "mín:", datos["temperature_2m_min"][i],
          "máx:", datos["temperature_2m_max"][i],
          "lluvia:", datos["precipitation_sum"][i])

# --> La pagina solo da la información del tiempo en 16 dias vista, comprobamos lo que pasa cuando ponemos una fecha más lejana

# 4. Comprobamos el límite de 16 días

if False:
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat, "longitude": lon,
            "daily": "temperature_2m_max",
            "start_date": "2027-03-01",
            "end_date": "2027-03-05"
        }
    )
    print(r.status_code)   # devuelve 400 ya que la petición no es válida
    print(r.json())        # explica el motivo del error, que es que  la fecha puesta está fuera del rango permitido

"""
--> Para solucionar este problema podemos utilizar un Archive API, el cual da el tiempo real de fechas pasadas
Por lo que nosotros podemos hacer que para el momento en el que piden la consulta, si el viaje está para fuera del rango la aplicación
devuelva algo como 'el tiempo que hizo en esas fechas el año pasado fue ...'
También hay una Climate API que lo que da es una predicción
"""

# 5. Decir el tiempo que hizo en esa fecha el año anterior
# Ejemplo: si el viaje fuera del 10 al 14 de diciembre de 2026, mostraríamos el tiempo de esas mismas fechas en 2025

r = requests.get(
    "https://archive-api.open-meteo.com/v1/archive",
    params={
        "latitude": lat, "longitude": lon,
        "start_date": "2025-12-10",
        "end_date": "2025-12-14",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto"
    }
)
print(r.status_code)
print(r.json()["daily"])

"""
Para mirar a mano el funcionamiento de la API:

  - Weather forecast API (mirar el tiempo en una vision de 16 dias): https://open-meteo.com/en/docs
  - Geocoding API (sacar las coordenadas): https://open-meteo.com/en/docs/geocoding-api
  - Historical weather API (mirar le tiempo en esas fechas el año pasado): https://open-meteo.com/en/docs/historical-weather-api
"""


