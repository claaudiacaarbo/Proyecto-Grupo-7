# Open-Meteo

import requests
from datetime import datetime, date

TIMEOUT = 10


def _parsear_fecha(valor):
    if isinstance(valor, date):
        return valor
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(valor, formato).date()
        except ValueError:
            pass
    raise ValueError(f"Formato de fecha no válido: {valor}")


def _un_anyo_antes(f):
    try:
        return f.replace(year=f.year - 1)
    except ValueError:  # 29 de febrero
        return f.replace(year=f.year - 1, day=28)


def obtener_tiempo(ciudad_destino, pais_destino, fecha_ida, fecha_vuelta):
    try:
        fecha_ida = _parsear_fecha(fecha_ida)
        fecha_vuelta = _parsear_fecha(fecha_vuelta)

        if fecha_vuelta < fecha_ida:
            raise ValueError("La fecha de vuelta no puede ser anterior a la de ida.")

        # 1. Coordenadas
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": ciudad_destino, 
                    "count": 10, 
                    "language": "es"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        resultados = r.json().get("results", [])

        lugar = next(
            (x for x in resultados
             if x.get("country", "").lower() == pais_destino.lower()),
            None,
        )
        if lugar is None:
            raise ValueError("No se ha encontrado la ciudad en el país indicado.")

        # 2. Elegir API
        hoy = date.today()
        
        if fecha_ida >= hoy and (fecha_vuelta - hoy).days <= 15:
            url_tiempo = "https://api.open-meteo.com/v1/forecast"
            inicio, fin = fecha_ida, fecha_vuelta
            fuente = "Previsión (Forecast API)"
            aviso = None
        
        else:
            url_tiempo = "https://archive-api.open-meteo.com/v1/archive"
            inicio = _un_anyo_antes(fecha_ida)
            fin = _un_anyo_antes(fecha_vuelta)
            fuente = "Datos históricos del año anterior (Archive API)"
            aviso = "Los datos corresponden al año anterior y son orientativos."

        r = requests.get(
            url_tiempo,
            params={
                "latitude": lugar["latitude"],
                "longitude": lugar["longitude"],
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "start_date": inicio.isoformat(),
                "end_date": fin.isoformat(),
                "timezone": "auto",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        datos = r.json()

        if "daily" not in datos:
            raise ValueError("La API no ha devuelto datos meteorológicos.")

        d = datos["daily"]
        dias = [
            {
                "fecha": dia,
                "temperatura_minima": d["temperature_2m_min"][i],
                "temperatura_maxima": d["temperature_2m_max"][i],
                "precipitaciones": d["precipitation_sum"][i],
            }
            for i, dia in enumerate(d["time"])
        ]

        return {
            "ciudad": lugar["name"],
            "pais": lugar["country"],
            "fuente": fuente,
            "aviso": aviso,
            "dias": dias,
        }

    except requests.exceptions.RequestException as error:
        raise RuntimeError(f"Error al conectar con Open-Meteo: {error}")
