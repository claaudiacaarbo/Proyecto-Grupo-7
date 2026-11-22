"""Planificador de viajes del grupo 7. Ejecutar con py -X utf8 planificador.py."""

import os
import re
from datetime import date, datetime
from decimal import Decimal
from functools import cache
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


PROYECTO = Path(__file__).resolve().parent
MODULOS = Path("modulos")
RESERVAS = MODULOS / "reservas.py"
MAPAS = MODULOS / "rutas.py"
TIEMPO = MODULOS / "tiempo.py"
WIKIVOYAGE = MODULOS / "wikivoyage.py"


def localizar_edge():
    # Windows puede conservar el navegador en EdgeCore sin el ejecutable habitual.
    if os.name != "nt" or os.getenv("SE_EDGE_PATH") or os.getenv("SE_BROWSER_PATH"):
        return
    edge = None
    version_mas_reciente = ()
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        carpeta = os.getenv(variable)
        if not carpeta:
            continue
        microsoft = Path(carpeta) / "Microsoft"
        ruta_normal = microsoft / "Edge" / "Application" / "msedge.exe"
        if ruta_normal.is_file():
            return

        for ruta in (microsoft / "EdgeCore").glob("*/msedge.exe"):
            version = ruta.parent.name
            if ruta.is_file() and re.fullmatch(r"\d+(?:\.\d+)*", version):
                numeros = tuple(map(int, version.split(".")))
                if numeros > version_mas_reciente:
                    edge = ruta
                    version_mas_reciente = numeros
    if edge is not None:
        os.environ["SE_BROWSER_PATH"] = str(edge)


@cache
def cargar_modulo(archivo):
    # Vuelos, alojamiento y coche comparten el mismo archivo.
    ruta = PROYECTO / archivo
    especificacion = spec_from_file_location(ruta.stem, ruta)
    if especificacion is None or especificacion.loader is None:
        raise ImportError(f"No se pudo cargar {ruta.name}.")
    modulo = module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    if archivo == RESERVAS:
        localizar_edge()
    return modulo


def pedir_texto(mensaje):
    while True:
        texto = input(mensaje).strip()
        if texto:
            return texto
        print("Este dato es obligatorio.")


def pedir_fecha(mensaje, fecha_minima, aviso):
    while True:
        texto = input(f"{mensaje} (DD/MM/AAAA o AAAA-MM-DD): ").strip()
        formato = "%d/%m/%Y" if "/" in texto else "%Y-%m-%d"
        try:
            fecha = datetime.strptime(texto, formato).date()
        except ValueError:
            print("Introduce una fecha válida.")
            continue
        if fecha >= fecha_minima:
            return fecha
        print(aviso)


def pedir_entero_positivo(mensaje, aviso):
    while True:
        try:
            numero = int(input(mensaje).strip())
            if numero > 0:
                return numero
        except ValueError:
            pass
        print(aviso)


def pedir_hora_opcional(mensaje):
    while True:
        texto = input(mensaje).strip()
        if not texto:
            return None
        try:
            datetime.strptime(texto, "%H:%M")
            if re.fullmatch(r"\d{2}:\d{2}", texto):
                return texto
        except ValueError:
            pass
        print("Introduce la hora en formato HH:MM o déjala en blanco.")


def pedir_intervalo_horario(etiqueta):
    while True:
        hora_min = pedir_hora_opcional(
            f"Hora mínima de salida de {etiqueta} HH:MM (opcional): "
        )
        hora_max = pedir_hora_opcional(
            f"Hora máxima de salida de {etiqueta} HH:MM (opcional): "
        )
        if hora_min and hora_max and hora_min > hora_max:
            print("La hora mínima no puede ser posterior a la máxima.")
            continue
        return hora_min, hora_max


def pedir_cabina():
    opciones = {"turista", "premium", "business", "primera"}
    while True:
        texto = input(
            "Cabina: turista, premium, business o primera (opcional): "
        ).strip().casefold()
        if not texto:
            return None
        if texto in opciones:
            return texto
        print("Elige turista, premium, business o primera, o déjalo en blanco.")


def pedir_entero_opcional(mensaje, predeterminado, minimo=1):
    while True:
        texto = input(mensaje).strip()
        if not texto:
            return predeterminado
        try:
            numero = int(texto)
            if numero >= minimo:
                return numero
        except ValueError:
            pass
        print(f"Introduce un número entero igual o mayor que {minimo}.")


def pedir_si_opcional(mensaje):
    while True:
        texto = input(mensaje).strip().casefold()
        if texto in ("", "n", "no"):
            return False
        if texto in ("s", "si", "sí"):
            return True
        print("Escribe s para exigirlo o pulsa Intro para no aplicarlo.")


def pedir_transmision():
    while True:
        texto = input("Transmisión manual o automática (opcional): ").strip().casefold()
        if not texto:
            return None
        if texto in ("manual", "automatica", "automática"):
            return "automatica" if texto.startswith("auto") else "manual"
        print("Escribe manual, automática o déjalo en blanco.")


def pedir_presupuesto():
    while True:
        texto = input("Presupuesto total en euros: ").strip()
        if re.fullmatch(r"[0-9]+(?:[.,][0-9]{1,2})?", texto):
            return Decimal(texto.replace(",", "."))
        print("Introduce un importe como 900 o 900,50.")


def pedir_alquiler():
    while True:
        respuesta = input("¿Alquilar coche? (s/n): ").strip().lower()
        if respuesta in ("s", "sí", "si"):
            return True
        if respuesta in ("n", "no"):
            return False
        print("Responde sí o no.")


def euros(importe):
    return f"{importe:.2f}".replace(".", ",") + " €"


def seccion(titulo, mostrar, *argumentos):
    print(f"\n--- {titulo} ---", flush=True)
    try:
        return mostrar(*argumentos)
    except Exception as error:
        # Si falla un proveedor, el planificador sigue con las demás consultas.
        print(f"Consulta no disponible. {error}")
        return None


def precio_total(oferta):
    if not oferta or not oferta.get("precio_total"):
        print("Precio no disponible.")
        return None
    importe = Decimal(oferta["precio_total"].removeprefix("EUR "))
    if not importe.is_finite() or importe < 0:
        raise ValueError("El proveedor devolvió un importe no válido.")
    print(f"Precio total del grupo: {euros(importe)}")
    return importe


def mostrar_vuelos(origen, destino, fechas, viajeros, filtros_vuelo):
    print("Buscando vuelos en Google Vuelos…", flush=True)
    vuelo = cargar_modulo(RESERVAS).buscar_vuelo(
        origen, destino, *fechas, viajeros,
        filtros_vuelo[0], filtros_vuelo[1],
        filtros_vuelo[2], filtros_vuelo[3], filtros_vuelo[4],
    )
    if not vuelo:
        return None
    for tramo in ("ida", "vuelta"):
        detalle = vuelo[tramo]
        print(f"{tramo.capitalize()}: {detalle['aerolinea']} | "
              f"{detalle['salida']} → {detalle['llegada']} | {detalle['duracion']}")
    if vuelo.get("precio_persona"):
        print(f"Precio por persona: {vuelo['precio_persona']}")
    if vuelo.get("precio_total"):
        return precio_total(vuelo)
    return None


def mostrar_alojamiento(destino, fechas, viajeros, noches, habitaciones,
                        desayuno, parking):
    if noches == 0:
        print("Viaje sin pernoctación.")
        return None
    oferta = cargar_modulo(RESERVAS).buscar_alojamiento(
        destino, *fechas, viajeros, habitaciones, desayuno, parking
    )
    if oferta:
        print(oferta["nombre"])
    return precio_total(oferta)


def mostrar_coche(destino, fechas, viajeros, alquilar, edad, asientos,
                  transmision):
    if not alquilar:
        print("Alquiler no solicitado.")
        return None
    if fechas[0] == fechas[1]:
        print("El módulo no cotiza alquileres para el mismo día.")
        return None
    oferta = cargar_modulo(RESERVAS).buscar_coche(
        destino, *fechas, viajeros, asientos, transmision
    )
    if oferta:
        print(oferta["nombre"])
        print(f"Estimación. Confirma con el proveedor si hay suplemento a los {edad} años.")
    return precio_total(oferta)


def mostrar_tiempo(ciudad, pais, fechas):
    tiempo = cargar_modulo(TIEMPO).obtener_tiempo(ciudad, pais, *fechas)
    print(tiempo["fuente"])
    if tiempo["aviso"]:
        print(tiempo["aviso"])
    if not tiempo["dias"]:
        print("No hay datos meteorológicos para las fechas consultadas.")
    for dia in tiempo["dias"]:
        valores = []
        for campo, etiqueta, unidad in (
            ("temperatura_minima", "mín.", "°C"),
            ("temperatura_maxima", "máx.", "°C"),
            ("precipitaciones", "lluvia", "mm"),
        ):
            valor = dia[campo]
            dato = f"{valor} {unidad}" if valor is not None else "sin datos"
            valores.append(f"{etiqueta} {dato}")
        print(dia["fecha"], " | ".join(valores))


def mostrar_visitas(ciudad, pais):
    guia = cargar_modulo(WIKIVOYAGE)
    fichas = guia.obtener_wikivoyage(ciudad, pais)
    if fichas:
        guia.mostrar_resultados(fichas)
    else:
        print("Wikivoyage no tiene fichas para este destino.")
    return fichas


def mostrar_ruta(ciudad, pais, fichas):
    lugares = [ficha for ficha in (fichas or []) if ficha["tipo"] == "Punto de interés"]
    if not lugares:
        print("No hay puntos de interés disponibles para calcular la ruta.")
        return

    print(f"Buscando las paradas de la ruta a pie en {ciudad}…", flush=True)
    mapas = cargar_modulo(MAPAS)
    centro = mapas.geocodificar(f"{ciudad}, {pais}")
    if centro is None:
        print("No se encontró el centro del destino.")
        return

    puntos = []
    for lugar in lugares[:mapas.MAX_LUGARES]:
        coordenadas = mapas.geocodificar_lugar(lugar, ciudad, pais)
        if coordenadas is not None:
            latitud, longitud = coordenadas
            puntos.append({"nombre": lugar["nombre"], "lat": latitud, "lon": longitud})
    puntos = mapas.ordenar_puntos(mapas.filtrar_puntos(puntos, centro))
    for numero, punto in enumerate(puntos, 1):
        print(f"{numero}. {punto['nombre']}")
    ruta = None
    if len(puntos) >= 2:
        print("Calculando la distancia y el tiempo a pie…", flush=True)
        ruta = mapas.calcular_ruta(puntos, "a pie")
        print(f"Ruta a pie: {ruta['km_total']} km | {ruta['minutos_total']} min")
    else:
        print("Se necesitan al menos dos paradas para calcular la ruta.")

    mapa = mapas.crear_mapa(puntos, ruta)
    if mapa:
        print(f"Mapa HTML guardado en: {mapa}")
        print("Ábrelo con un navegador para ver los puntos y la ruta.")


def mostrar_presupuesto(presupuesto, cotizaciones):
    print("\n--- PRESUPUESTO ---")
    print(f"Presupuesto del grupo: {euros(presupuesto)}")
    faltan = [servicio for servicio, precio in cotizaciones.items() if precio is None]
    precios = [precio for precio in cotizaciones.values() if precio is not None]
    if precios:
        subtotal = sum(precios, Decimal(0))
        etiqueta = "Subtotal parcial" if faltan else "Subtotal cotizado"
        print(f"{etiqueta}: {euros(subtotal)}")
        diferencia = presupuesto - subtotal
        if diferencia < 0:
            print(f"Los precios disponibles superan el presupuesto en {euros(-diferencia)}.")
        elif faltan:
            print(f"Quedan {euros(diferencia)} antes de contar los importes pendientes.")
        else:
            print(f"Margen respecto al presupuesto: {euros(diferencia)}.")
    else:
        print("Subtotal no disponible.")
    if faltan:
        print("Sin cotización: " + ", ".join(faltan) + ".")
    print("Los precios de la guía se muestran en sus fichas.")


def planificar_viaje(datos):
    """Muestra el resumen a partir de los datos recogidos en la terminal."""
    ciudad = datos["ciudad_destino"]
    pais = datos["pais_destino"]
    origen = f"{datos['ciudad_origen']}, {datos['pais_origen']}"
    destino = f"{ciudad}, {pais}"
    ida, vuelta = datos["fecha_ida"], datos["fecha_vuelta"]
    fechas = (ida.isoformat(), vuelta.isoformat())
    noches = (vuelta - ida).days
    viajeros = datos["num_viajeros"]
    alquilar = datos["alquilar_coche"]

    print(f"\nViaje de {origen} a {destino}")
    print(f"Del {ida:%d/%m/%Y} al {vuelta:%d/%m/%Y} | "
          f"Días: {noches + 1} | Noches: {noches} | Viajeros: {viajeros}")
    vuelo = seccion("VUELOS", mostrar_vuelos, origen, destino, fechas, viajeros,
                    datos["filtros_vuelo"])
    if vuelo is None:
        print("Precio del vuelo no disponible. Continuando con el alojamiento", flush=True)
    alojamiento = seccion(
        "ALOJAMIENTO", mostrar_alojamiento, destino, fechas, viajeros, noches,
        datos["habitaciones"], datos["desayuno"], datos["parking"],
    )
    coche = seccion("COCHE", mostrar_coche, destino, fechas, viajeros, alquilar,
                    datos["edad_conductor"], datos["asientos"],
                    datos["transmision"])
    seccion("TIEMPO", mostrar_tiempo, ciudad, pais, fechas)
    fichas = seccion("VISITAS Y GASTRONOMÍA", mostrar_visitas, ciudad, pais)
    seccion("RUTAS", mostrar_ruta, ciudad, pais, fichas)

    cotizaciones = {"vuelos": vuelo}
    if noches:
        cotizaciones["alojamiento"] = alojamiento
    if alquilar:
        cotizaciones["coche"] = coche
    mostrar_presupuesto(datos["presupuesto"], cotizaciones)


def main():
    print("PLANIFICADOR DE VIAJES")
    print("Responde a las preguntas del viaje y pulsa Intro después de cada respuesta.")
    print("Edge se abrirá para buscar precios. El resumen sale en esta terminal.\n")
    hoy = date.today()
    try:
        datos = {
            "ciudad_origen": pedir_texto("Ciudad de origen: "),
            "pais_origen": pedir_texto("País de origen: "),
            "ciudad_destino": pedir_texto("Ciudad de destino: "),
            "pais_destino": pedir_texto("País de destino: "),
        }
        datos["fecha_ida"] = pedir_fecha("Fecha de ida", hoy,
                                        "La fecha de ida debe ser hoy o posterior.")
        datos["fecha_vuelta"] = pedir_fecha("Fecha de vuelta", datos["fecha_ida"],
                                           "La vuelta debe ser el mismo día que la ida o después.")
        datos["num_viajeros"] = pedir_entero_positivo(
            "Número de viajeros: ", "Introduce un número entero mayor que cero.")
        print("\nFILTROS OPCIONALES DE VUELO")
        hora_ida = pedir_intervalo_horario("la ida")
        hora_vuelta = pedir_intervalo_horario("la vuelta")
        cabina = pedir_cabina()
        datos["filtros_vuelo"] = (*hora_ida, *hora_vuelta, cabina)

        print("\nFILTROS OPCIONALES DE ALOJAMIENTO")
        datos["habitaciones"] = pedir_entero_opcional(
            "Número de habitaciones (opcional, por defecto 1): ", 1
        )
        datos["desayuno"] = pedir_si_opcional(
            "Exigir desayuno incluido (opcional, escriba s si lo necesitas): "
        )
        datos["parking"] = pedir_si_opcional(
            "Exigir parking gratuito (opcional, escriba s si lo necesitas): "
        )

        datos["presupuesto"] = pedir_presupuesto()
        datos["alquilar_coche"] = pedir_alquiler()
        datos["edad_conductor"] = None
        datos["asientos"] = datos["num_viajeros"]
        datos["transmision"] = None
        if datos["alquilar_coche"]:
            datos["edad_conductor"] = pedir_entero_positivo(
                "Edad del conductor: ", "Introduce una edad en años mayor que cero.")
            datos["asientos"] = pedir_entero_opcional(
                "Asientos mínimos (opcional, por defecto mayor o igual a número de viajeros): ",
                datos["num_viajeros"], minimo=datos["num_viajeros"],
            )
            datos["transmision"] = pedir_transmision()
        planificar_viaje(datos)
    except (EOFError, KeyboardInterrupt):
        print("\nViaje cancelado.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
