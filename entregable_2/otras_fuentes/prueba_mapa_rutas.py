#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 23 14:32:03 2026

@author: isaacruiz

Prueba rápida: ¿podemos sacar datos de Nominatim (coordenadas) y OSRM (rutas)?
"""

import time
import requests

HEADERS = {"User-Agent": "proyecto-clase-planificador-viajes/1.0"}  # Nominatim lo exige

LUGARES = [
    "Estación Joaquín Sorolla, Valencia",
    "Catedral de Valencia",
    "Mercado Central, Valencia",
    "Ciudad de las Artes y las Ciencias, Valencia",
]

# El servidor demo de OSRM solo ofrece coche.
# Para ir a pie: routing.openstreetmap.de (su URL usa "driving" como nombre de perfil).
OSRM = {
    "coche": "https://router.project-osrm.org/route/v1/driving/",
    "a pie": "https://routing.openstreetmap.de/routed-foot/route/v1/driving/",
}


def geocodificar(nombre):
    """Nombre de lugar -> (lat, lon) con Nominatim."""
    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": nombre, "format": "json", "limit": 1},
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    datos = r.json()
    if not datos:
        return None
    return float(datos[0]["lat"]), float(datos[0]["lon"])


def ruta(puntos, modo):
    """Lista de (lat, lon) -> distancia y duración totales y por tramo."""
    coords = ";".join(f"{lon},{lat}" for lat, lon in puntos)
    r = requests.get(
        OSRM[modo] + coords,
        params={"overview": "false"},
        headers=HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    datos = r.json()
    if datos.get("code") != "Ok":
        raise RuntimeError(f"OSRM respondió: {datos.get('code')} {datos.get('message', '')}")
    return datos["routes"][0]


def main():
    print("=== 1. Geocodificación con Nominatim ===")
    puntos = []
    for nombre in LUGARES:
        try:
            coord = geocodificar(nombre)
        except Exception as e:
            print(f"  ERROR en '{nombre}': {e}")
            coord = None
        if coord:
            print(f"  OK  {nombre}: {coord[0]:.4f}, {coord[1]:.4f}")
            puntos.append(coord)
        else:
            print(f"  --  sin resultado para '{nombre}'")
        time.sleep(1.1)  # Nominatim: máximo 1 petición por segundo

    if len(puntos) < 2:
        print("\nNo hay suficientes puntos para calcular una ruta.")
        return

    print("\n=== 2. Rutas con OSRM ===")
    for modo in OSRM:
        try:
            r = ruta(puntos, modo)
            print(f"\n  {modo.upper()}: {r['distance'] / 1000:.1f} km, {r['duration'] / 60:.0f} min")
            for i, tramo in enumerate(r["legs"], 1):
                print(f"    tramo {i}: {tramo['distance'] / 1000:.1f} km, {tramo['duration'] / 60:.0f} min")
        except Exception as e:
            print(f"\n  {modo.upper()}: ERROR -> {e}")


if __name__ == "__main__":
    main()