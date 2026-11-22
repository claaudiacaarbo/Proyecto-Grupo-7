# -*- coding: utf-8 -*-
"""
Grupo 7. Módulo de mapa y rutas.
Autor: Isaac Ruiz Quiterio

Qué hace:
  1. Pide al usuario la ciudad y el país de destino.
  2. Obtiene los puntos de interés de esa ciudad desde el módulo de Wikivoyage
     (o, si no se puede, desde el CSV que genera ese módulo).
  3. Convierte cada lugar en coordenadas con Nominatim (OpenStreetMap).
  4. Filtra los datos: limpia direcciones, quita duplicados y descarta
     lugares que Nominatim sitúa fuera de la ciudad.
  5. Ordena los lugares para que la ruta tenga sentido y calcula con OSRM
     la distancia y el tiempo a pie o en coche.
  6. Muestra el resultado por terminal y genera un mapa interactivo
     (mapa_ruta.html) con folium, que usa Leaflet y OpenStreetMap.

Librerías necesarias:
  python -m pip install requests folium
"""

import csv
import math
import time
import unicodedata
from pathlib import Path

import requests


# 1. CONSTANTES

# Nominatim exige identificarse con un User-Agent propio.
HEADERS = {"User-Agent": "ATD-Grupo7-planificador-viajes/1.0 (uso academico UPV)"}

URL_NOMINATIM = "https://nominatim.openstreetmap.org/search"

# El servidor demo de OSRM solo ofrece coche.
# Para ir a pie usamos routing.openstreetmap.de (su URL usa "driving" como
# nombre de perfil, pero el servidor "routed-foot" calcula rutas a pie).
URL_OSRM = {
    "coche": "https://router.project-osrm.org/route/v1/driving/",
    "a pie": "https://routing.openstreetmap.de/routed-foot/route/v1/driving/",
}

CARPETA = Path(__file__).resolve().parent
CSV_WIKIVOYAGE = CARPETA / "resultados_wikivoyage" / "datos_wikivoyage.csv"
ARCHIVO_MAPA = CARPETA / "mapa_ruta.html"

KM_MAXIMOS_AL_CENTRO = 15   # Un lugar más lejos que esto no es de la ciudad
MAX_LUGARES = 8             # Nominatim admite 1 petición/s: limitamos la espera


# 2. FILTRADO Y NORMALIZACIÓN DE TEXTOS

def quitar_tildes(texto):
    """'Roma, Itália' -> 'roma, italia'. Sirve para comparar textos."""
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(letra for letra in texto if unicodedata.category(letra) != "Mn")
    return texto.casefold()


def normalizar_entrada(texto):
    """Limpia lo que escribe el usuario: '  roma ' -> 'Roma'."""
    return " ".join(texto.split()).title()


def limpiar_direccion(direccion, ciudad):
    """
    Deja la dirección de Wikivoyage lista para buscarla en Nominatim.
    Ejemplos:
      'Piazzale del Colosseo / Via dei Fori Imperiali' -> 'Piazzale del Colosseo'
      'Piazzale del Museo Borghese (Parco di Villa Borghese)' -> 'Piazzale del Museo Borghese'
      'Piazza di Trevi, Roma' -> 'Piazza di Trevi'
    """
    if not direccion:
        return ""
    direccion = direccion.split("/")[0]           # Si hay dos calles, nos quedamos con la primera
    if "(" in direccion:                          # Quitamos lo que va entre paréntesis
        direccion = direccion[:direccion.find("(")]
    partes = [p.strip() for p in direccion.split(",")]
    partes = [p for p in partes if quitar_tildes(p) != quitar_tildes(ciudad)]  # Quitamos la ciudad repetida
    return " ".join(", ".join(partes).split())


# 3. OBTENER LOS LUGARES DEL MÓDULO DE WIKIVOYAGE

def leer_lugares_wikivoyage(ciudad_destino, pais_destino, tipos=("Punto de interés",)):
    """
    Devuelve una lista de diccionarios {'nombre', 'direccion', 'tipo'}.
    Primero intenta llamar a la función del módulo wikivoyage.py.
    Si no está disponible o falla, lee el CSV que guarda ese módulo.
    """
    registros = []
    try:
        import wikivoyage
        registros = wikivoyage.obtener_wikivoyage(ciudad_destino, pais_destino)
        if registros:
            print("Lugares obtenidos del módulo de Wikivoyage.")
    except Exception as error:
        print("No se pudo usar el módulo de Wikivoyage (" + str(error) + ").")

    if not registros and CSV_WIKIVOYAGE.exists():
        ciudad = quitar_tildes(ciudad_destino)
        with CSV_WIKIVOYAGE.open(encoding="utf-8-sig", newline="") as fichero:
            registros = [
                fila for fila in csv.DictReader(fichero, delimiter=";")
                if quitar_tildes(fila["ciudad"]) == ciudad
            ]
        print("Lugares leídos del CSV:", CSV_WIKIVOYAGE.name)

    lugares = []
    for fila in registros:
        if fila["tipo"] not in tipos:
            continue
        lugares.append({"nombre": fila["nombre"].strip(),
                        "direccion": fila["direccion"].strip(),
                        "tipo": fila["tipo"]})
    return lugares


# 4. GEOCODIFICACIÓN CON NOMINATIM

def geocodificar(consulta):
    """Texto -> (lat, lon) como números float, o None si no hay resultado."""
    respuesta = requests.get(URL_NOMINATIM,
                             params={"q": consulta, "format": "json", "limit": 1},
                             headers=HEADERS, timeout=15)
    respuesta.raise_for_status()
    datos = respuesta.json()
    time.sleep(1.1)   # Límite de Nominatim: 1 petición por segundo
    if not datos:
        return None
    # Nominatim devuelve las coordenadas como texto ("41.89"): las pasamos a float
    return float(datos[0]["lat"]), float(datos[0]["lon"])


def geocodificar_lugar(lugar, ciudad, pais):
    """
    Busca un lugar probando primero con su dirección limpia y, si no
    sale nada, con su nombre. Siempre añadimos ciudad y país para que
    no encuentre un 'Panteón' de otro sitio.
    """
    intentos = []
    direccion = limpiar_direccion(lugar["direccion"], ciudad)
    if direccion:
        intentos.append(direccion + ", " + ciudad + ", " + pais)
    intentos.append(lugar["nombre"] + ", " + ciudad + ", " + pais)

    for consulta in intentos:
        try:
            coordenadas = geocodificar(consulta)
        except requests.RequestException as error:
            print("  Error consultando Nominatim:", error)
            return None
        if coordenadas is not None:
            return coordenadas
    return None


# 5. FILTRADO DE LOS PUNTOS Y ORDEN DE LA RUTA

def distancia_km(punto_a, punto_b):
    """Distancia en línea recta entre dos (lat, lon) con la fórmula de Haversine."""
    lat1, lon1 = map(math.radians, punto_a)
    lat2, lon2 = map(math.radians, punto_b)
    a = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def filtrar_puntos(puntos, centro, km_maximos=KM_MAXIMOS_AL_CENTRO):
    """
    Quita los puntos que no sirven:
      - los que están demasiado lejos del centro de la ciudad (error de Nominatim)
      - los repetidos (mismas coordenadas redondeadas a 4 decimales, unos 10 m)
    """
    filtrados = []
    vistos = set()
    for punto in puntos:
        clave = (round(punto["lat"], 4), round(punto["lon"], 4))
        if clave in vistos:
            print("  Descartado por repetido:", punto["nombre"])
            continue
        lejania = distancia_km(centro, (punto["lat"], punto["lon"]))
        if lejania > km_maximos:
            print(f"  Descartado por estar a {lejania:.0f} km del centro:", punto["nombre"])
            continue
        vistos.add(clave)
        filtrados.append(punto)
    return filtrados


def ordenar_puntos(puntos):
    """
    Ordena por 'vecino más cercano': empieza en el primero y siempre va
    al lugar más próximo que queda. Así la ruta no da saltos de un lado
    a otro de la ciudad.
    """
    if not puntos:
        return []
    pendientes = puntos[1:]
    ordenados = [puntos[0]]
    while pendientes:
        actual = (ordenados[-1]["lat"], ordenados[-1]["lon"])
        siguiente = min(pendientes, key=lambda p: distancia_km(actual, (p["lat"], p["lon"])))
        ordenados.append(siguiente)
        pendientes.remove(siguiente)
    return ordenados


# 6. RUTA CON OSRM

def calcular_ruta(puntos, modo):
    """
    Pide a OSRM la ruta que pasa por todos los puntos en orden.
    OSRM devuelve metros y segundos; los pasamos a km y minutos.
    """
    # OSRM quiere las coordenadas como "lon,lat;lon,lat;..." (al revés que Nominatim)
    coordenadas = ";".join(f"{p['lon']},{p['lat']}" for p in puntos)
    respuesta = requests.get(URL_OSRM[modo] + coordenadas,
                             params={"overview": "full", "geometries": "geojson"},
                             headers=HEADERS, timeout=30)
    respuesta.raise_for_status()
    datos = respuesta.json()
    if datos.get("code") != "Ok":
        raise RuntimeError("OSRM respondió: " + str(datos.get("code")))

    ruta = datos["routes"][0]
    tramos = []
    for i, tramo in enumerate(ruta["legs"]):
        tramos.append({"desde": puntos[i]["nombre"],
                       "hasta": puntos[i + 1]["nombre"],
                       "km": round(tramo["distance"] / 1000, 2),
                       "minutos": round(tramo["duration"] / 60)})
    # La línea de la ruta viene como [lon, lat]; folium la quiere como [lat, lon]
    linea = [[lat, lon] for lon, lat in ruta["geometry"]["coordinates"]]
    return {"modo": modo,
            "km_total": round(ruta["distance"] / 1000, 2),
            "minutos_total": round(ruta["duration"] / 60),
            "tramos": tramos,
            "linea": linea}


# 7. MAPA CON FOLIUM (LEAFLET + OPENSTREETMAP)

def crear_mapa(puntos, ruta, archivo=ARCHIVO_MAPA):
    """Genera un HTML con un marcador numerado por lugar y la línea de la ruta."""
    try:
        import folium
    except ImportError:
        print("Falta folium (python -m pip install folium). No se genera el mapa.")
        return None

    mapa = folium.Map(location=[puntos[0]["lat"], puntos[0]["lon"]], zoom_start=14)
    for numero, punto in enumerate(puntos, start=1):
        folium.Marker([punto["lat"], punto["lon"]],
                      popup=f"{numero}. {punto['nombre']}",
                      tooltip=f"{numero}. {punto['nombre']}").add_to(mapa)
    if ruta and ruta["linea"]:
        folium.PolyLine(ruta["linea"], weight=4, opacity=0.8).add_to(mapa)
    mapa.save(str(archivo))
    return archivo


# 8. FUNCIÓN PRINCIPAL DEL MÓDULO (la que llamará el programa común)

def obtener_mapa_y_rutas(ciudad_destino, pais_destino, modo="a pie", max_lugares=MAX_LUGARES):
    """
    Junta todos los pasos y devuelve un diccionario con:
      'puntos': lista ordenada de lugares con nombre, lat y lon
      'ruta': distancias y tiempos (total y por tramo)
      'mapa': ruta del archivo HTML generado (o None)
    """
    ciudad_destino = normalizar_entrada(ciudad_destino)
    pais_destino = normalizar_entrada(pais_destino)

    print("\nBuscando el centro de", ciudad_destino + "...")
    centro = geocodificar(ciudad_destino + ", " + pais_destino)
    if centro is None:
        raise ValueError("No se ha encontrado la ciudad " + ciudad_destino)

    lugares = leer_lugares_wikivoyage(ciudad_destino, pais_destino)
    if not lugares:
        raise ValueError("No hay puntos de interés para " + ciudad_destino)
    lugares = lugares[:max_lugares]

    print("\nGeocodificando", len(lugares), "lugares (1 por segundo)...")
    puntos = []
    for lugar in lugares:
        coordenadas = geocodificar_lugar(lugar, ciudad_destino, pais_destino)
        if coordenadas is None:
            print("  Sin coordenadas:", lugar["nombre"])
            continue
        print(f"  OK {lugar['nombre']}: {coordenadas[0]:.4f}, {coordenadas[1]:.4f}")
        puntos.append({"nombre": lugar["nombre"], "lat": coordenadas[0], "lon": coordenadas[1]})

    print("\nFiltrando puntos...")
    puntos = filtrar_puntos(puntos, centro)
    puntos = ordenar_puntos(puntos)

    ruta = None
    if len(puntos) >= 2:
        try:
            ruta = calcular_ruta(puntos, modo)
        except (requests.RequestException, RuntimeError) as error:
            print("No se pudo calcular la ruta:", error)

    mapa = crear_mapa(puntos, ruta) if puntos else None
    return {"ciudad": ciudad_destino, "puntos": puntos, "ruta": ruta, "mapa": mapa}


# 9. PROGRAMA POR TERMINAL

def main():
    print("MAPA Y RUTAS - GRUPO 7")

    # Pedir los datos (con los nombres de parámetro comunes del grupo)
    ciudad_destino = input("Ciudad de destino: ")
    pais_destino = input("País de destino: ")
    modo = input("¿Ruta a pie o en coche? [a pie/coche]: ").strip().lower()
    if modo not in URL_OSRM:   # Cualquier otra respuesta se toma como 'a pie'
        modo = "a pie"

    try:
        resultado = obtener_mapa_y_rutas(ciudad_destino, pais_destino, modo)
    except (requests.RequestException, ValueError) as error:
        print("No se ha podido completar la ruta:", error)
    else:
        # Mostrar el resultado
        print("\n" + "=" * 50)
        print("RUTA POR", resultado["ciudad"].upper())
        print("=" * 50)
        for numero, punto in enumerate(resultado["puntos"], start=1):
            print(f"{numero}. {punto['nombre']}")

        ruta = resultado["ruta"]
        if ruta:
            print(f"\nRecorrido {ruta['modo']}: {ruta['km_total']} km, {ruta['minutos_total']} min")
            for tramo in ruta["tramos"]:
                print(f"  {tramo['desde']} -> {tramo['hasta']}: {tramo['km']} km, {tramo['minutos']} min")
        if resultado["mapa"]:
            print("\nMapa guardado en:", resultado["mapa"])
            print("Ábrelo con el navegador.")
if __name__ == "__main__":
    main()