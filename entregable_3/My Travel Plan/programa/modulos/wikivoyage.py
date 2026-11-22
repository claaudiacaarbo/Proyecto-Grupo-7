# Grupo 7. Gastronomía y puntos de interés de Wikivoyage.

import re
from decimal import Decimal
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup


# Configuración
API = "https://es.wikivoyage.org/w/api.php"
COLUMNAS = ["ciudad", "tipo", "nombre", "descripcion", "direccion",
            "horario", "precio", "telefono", "web", "fuente"]
APARTADOS = {
    "ver": "ver", "lugares de interés": "ver",
    "hacer": "hacer",
    "comer": "comer", "comer y beber": "comer",
    "beber": "beber", "beber y salir": "beber", "vida nocturna": "beber",
}
ETIQUETAS_DATOS = {
    "direccion": ["dirección:", "direccion:"],
    "horario": ["horario:", "horarios:"],
    "precio": ["precio medio por persona:", "precio medio:", "precio:"],
    "telefono": ["teléfono:"],
}
# Estas etiquetas cierran el campo anterior.
LIMITES_DATOS = [
    etiqueta for variantes in ETIQUETAS_DATOS.values() for etiqueta in variantes
] + ["reservas:", "web:"]

ALIAS_MONEDAS = {
    "EUR": ("€", "euro", "euros"),
    "USD": ("US$", "dólar estadounidense", "dólares estadounidenses"),
    "GBP": ("£", "libra esterlina", "libras esterlinas"),
    "JPY": ("JP¥", "yen", "yenes"),
    "CNY": ("CN¥", "yuan", "yuanes", "元"),
    "CAD": ("CA$", "C$", "dólar canadiense", "dólares canadienses"),
    "AUD": ("AU$", "A$", "dólar australiano", "dólares australianos"),
    "MXN": ("MX$", "peso mexicano", "pesos mexicanos"),
    "BRL": ("R$", "real brasileño", "reales brasileños"),
    "INR": ("₹", "rupia india", "rupias indias"),
    "CHF": ("franco suizo", "francos suizos"),
    "THB": ("฿", "baht"),
    "VND": ("₫", "dong", "dongs"),
    "PHP": ("₱", "peso filipino", "pesos filipinos"),
}
MONEDAS = {
    forma.lower(): codigo
    for codigo, formas in ALIAS_MONEDAS.items()
    for forma in (codigo, *formas)
}
for codigo in (
    "AED", "ARS", "CLP", "COP", "CRC", "CZK", "DKK", "EGP", "HKD", "HUF", "IDR",
    "ILS", "KRW", "MAD", "NOK", "NZD", "PEN", "PLN", "SEK", "SGD", "TRY", "TWD",
    "UYU", "ZAR",
):
    MONEDAS[codigo.lower()] = codigo
# Los símbolos ambiguos, como $, se guardan con moneda indeterminada.
MONEDAS.update(dict.fromkeys(("$", "¥", "dólar", "dólares", "peso", "pesos")))

# Priorizar marcas largas, como US$ antes que $.
FORMAS_MONEDA = "|".join(re.escape(forma) for forma in sorted(MONEDAS, key=len, reverse=True))
MONEDA = rf"(?<![^\W\d_])(?:{FORMAS_MONEDA})(?![^\W\d_])"
MONEDA_SUFIJO = rf"{MONEDA}(?!\s*\d)"
# Admite separadores de miles y decimales de varios formatos.
NUMERO_PRECIO = (
    r"(?:\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?"
    r"|\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
    r"(?!\d|[.,]\d)"
)
# Reconocer precios, intervalos y gratuidad.
PATRON_TARIFA = re.compile(
    rf"(?<![\w.,])(?P<entre>entre\s+)?"
    rf"(?:(?P<moneda_antes>{MONEDA})\s*)?(?P<importe>{NUMERO_PRECIO})"
    rf"(?:\s*(?P<moneda_despues>{MONEDA_SUFIJO}))?"
    rf"(?:\s*(?:[-–—]|\ba\b|\bhasta\b|(?(entre)\by\b|(?!)))\s*"
    rf"(?:(?P<moneda_final_antes>{MONEDA})\s*)?(?P<hasta>{NUMERO_PRECIO})"
    rf"(?:\s*(?P<moneda_final_despues>{MONEDA_SUFIJO}))?"
    r"(?!\s*(?:%|(?:años?|years?|días?|days?|personas?|people)\b)))?"
    r"|\b(?P<gratis>gratuit[oa]s?|gratis|sin (?:coste|costo|cargo)|no pagan?|free(?: of charge)?)\b",
    re.IGNORECASE,
)
# Separar tarifas sin cortar las comas decimales.
SEPARADORES_TARIFA = re.compile(
    r"(?:[;!?]|,(?!\d)|\.(?=\s|$))(?![^()]*\))|\s+(?=(?:(?:más|plus)\b(?!\s+de\b)|\+\s))",
    re.IGNORECASE,
)
# Evitar que «no es gratis» se lea como gratuidad.
NEGACION_GRATUIDAD = re.compile(r"\b(?:no|not)(?:\s+(?:es|son|será|is|are))?\s+$", re.IGNORECASE)


# INICIO DEL BLOQUE CON APOYO DE IA (OpenAI Codex, GPT-6, apartado 4.3)
def convertir_importe(numero):
    numero = "".join(numero.split())
    # Una o dos cifras tras el separador indican decimales.
    parte_decimal = re.search(r"[.,](\d{1,2})$", numero)
    if parte_decimal:
        entero = re.sub(r"[.,]", "", numero[:parte_decimal.start()])
        return Decimal(f"{entero}.{parte_decimal[1]}")
    return Decimal(re.sub(r"[.,]", "", numero))


def identificar_moneda(marcas):
    for marca in marcas:
        if MONEDAS[marca] is not None:
            return MONEDAS[marca]
    return None
# FIN DEL BLOQUE CON APOYO DE IA


def extraer_tarifas(precio):
    """Extrae importes orientativos y conserva las condiciones de la guía."""
    grupos = []
    inicio = 0
    for fin in [m.start() for m in SEPARADORES_TARIFA.finditer(precio)] + [len(precio)]:
        fragmento = precio[inicio:fin]
        tarifas = []
        for coincidencia in PATRON_TARIFA.finditer(fragmento):
            if coincidencia["gratis"]:
                if NEGACION_GRATUIDAD.search(fragmento[:coincidencia.start()]):
                    continue
                tarifas.append((Decimal(0), None, None))
                continue

            marcas_inicio = [marca.lower() for marca in (coincidencia["moneda_antes"],
                                                        coincidencia["moneda_despues"]) if marca]
            marcas_fin = [marca.lower() for marca in (coincidencia["moneda_final_antes"],
                                                     coincidencia["moneda_final_despues"]) if marca]
            # Excluir edades, fechas y otros números sin moneda.
            if not marcas_inicio and not marcas_fin:
                continue

            moneda_inicio = identificar_moneda(marcas_inicio)
            moneda_fin = identificar_moneda(marcas_fin)
            importe = convertir_importe(coincidencia["importe"])
            hasta = convertir_importe(coincidencia["hasta"]) if coincidencia["hasta"] else None
            if (marcas_inicio and marcas_fin
                    and (moneda_inicio or marcas_inicio[0]) != (moneda_fin or marcas_fin[0])):
                # Guardar por separado los importes de monedas distintas.
                tarifas.extend([(importe, moneda_inicio, None), (hasta, moneda_fin, None)])
            else:
                tarifas.append((importe, moneda_inicio or moneda_fin, hasta))
        if tarifas:
            grupos.append((inicio if grupos else 0, fin, tarifas))
        elif grupos:
            # Un fragmento sin importe puede matizar la tarifa anterior.
            principio, _, anteriores = grupos[-1]
            grupos[-1] = (principio, fin, anteriores)
        inicio = fin + 1 if fin < len(precio) else fin

    return [
        {"importe": importe, "moneda": moneda, "importe_hasta": hasta,
         "contexto": precio[inicio:fin].strip()}
        for inicio, fin, tarifas in grupos
        for importe, moneda, hasta in tarifas
    ]


# Lectura y organización de datos
def obtener_texto(etiqueta):
    if etiqueta is None:
        return ""
    texto = etiqueta.get_text(" ", strip=True)
    return " ".join(texto.split())


def buscar_campo(ficha, clases):
    for clase in clases:
        texto = obtener_texto(ficha.find(class_=clase))
        if texto != "":
            return texto
    return ""


def crear_fila(ciudad, tipo, nombre, descripcion, fuente):
    fila = dict.fromkeys(COLUMNAS, "")
    fila["ciudad"] = ciudad
    fila["tipo"] = tipo
    fila["nombre"] = nombre
    fila["descripcion"] = descripcion
    fila["fuente"] = fuente
    return fila


def buscar_dato(texto, etiquetas):
    # Buscar sin distinguir mayúsculas y conservar el texto original.
    texto_minusculas = texto.lower()
    for etiqueta in etiquetas:
        posicion = texto_minusculas.find(etiqueta)
        if posicion != -1:
            dato = texto[posicion + len(etiqueta):].strip()
            for otra_etiqueta in LIMITES_DATOS:
                final = dato.lower().find(otra_etiqueta)
                if final != -1:
                    dato = dato[:final].strip()
            return dato.split(". ", 1)[0]
    return ""


# Extracción de fichas
def extraer_fichas(sopa, ciudad, fuente):
    registros = []
    tipos = {"ver": "Punto de interés", "see": "Punto de interés",
             "hacer": "Actividad", "do": "Actividad",
             "comer": "Restaurante", "eat": "Restaurante",
             "beber": "Bar o local de ocio", "drink": "Bar o local de ocio"}

    for ficha in sopa.find_all(class_=["voy-vCard", "vcard"]):
        # Evitar fichas anidadas y menciones sueltas.
        if ficha.find_parent(class_=["voy-vCard", "vcard"]) is not None:
            continue
        if "voy-listing-inline" in ficha.get("class", []):
            continue
        # En «Cómo desplazarse» hay alquileres etiquetados como «see».
        encabezado = obtener_texto(ficha.find_previous("h2")).lower()
        apartado = APARTADOS.get(encabezado, "")
        if apartado == "":
            continue
        grupo = ficha.get("data-group", "").lower() or apartado
        tipo = tipos.get(grupo, "")
        nombre = buscar_campo(ficha, ["voy-listing-name", "listing-name", "fn"])
        if tipo == "" or nombre == "":
            continue

        descripcion = buscar_campo(ficha, ["voy-listing-content", "listing-content"])
        fila = crear_fila(ciudad, tipo, nombre, descripcion, fuente)
        fila["direccion"] = buscar_campo(ficha, ["voy-listing-address", "listing-address"])
        fila["horario"] = buscar_campo(ficha, ["voy-listing-hours", "listing-hours"])
        fila["horario"] = fila["horario"].replace("🕓", "").strip()
        fila["precio"] = buscar_campo(ficha, ["voy-listing-price", "listing-price"])
        if fila["precio"].startswith("Precio:"):
            fila["precio"] = fila["precio"][7:].strip()
        fila["telefono"] = buscar_campo(ficha, ["voy-listing-phone-number", "tel"])
        fila["web"] = ficha.get("data-url", "")
        if fila["web"] == "":
            enlace = ficha.find(class_=["voy-listing-name", "listing-name"])
            if enlace is not None:
                enlace = enlace.find("a", class_="external", href=True)
                if enlace is not None:
                    fila["web"] = enlace["href"]
        if fila["web"] != "":
            fila["web"] = urljoin(fuente, fila["web"])

        registros.append(fila)
    return registros


# Extracción de texto libre
def extraer_texto(sopa, ciudad, fuente):
    registros = []
    encabezado = ""
    apartado = ""
    subapartado = ""
    lista_de_platos = None
    tipo_de_lista = "Plato típico"
    numero = 0
    for etiqueta in sopa.find_all(["h2", "h3", "h4", "p", "li"]):
        contenido = obtener_texto(etiqueta)
        if etiqueta.name == "h2":
            encabezado = contenido.lower()
            apartado = APARTADOS.get(encabezado, "")
            subapartado = ""
            lista_de_platos = None
        elif etiqueta.name in ["h3", "h4"]:
            subapartado = contenido.lower()
            lista_de_platos = None
        elif apartado:
            # Las fichas ya se han procesado en extraer_fichas().
            if etiqueta.find_parent(class_=["voy-vCard", "vcard"]) is not None:
                continue
            if etiqueta.find(class_=["voy-vCard", "vcard"]) is not None:
                continue
            if "vcard" in etiqueta.get("class", []):
                continue
            if contenido == "" or etiqueta.find_parent(["li", "figure"]) is not None:
                continue

            numero += 1
            tipo = ""

            # La introducción solo describe la lista siguiente.
            if etiqueta.name == "p":
                lista_de_platos = None
                for frase in ["puedes pedir", "platos típicos", "platos autóctonos",
                              "bebidas típicas", "bebidas tradicionales"]:
                    if frase in contenido.lower():
                        siguiente = etiqueta.find_next_sibling()
                        if siguiente is not None and siguiente.name in ["ul", "ol"]:
                            lista_de_platos = siguiente
                            tipo_de_lista = "Plato típico"
                            if apartado != "comer" or "bebidas" in frase:
                                tipo_de_lista = "Bebida típica"
                if apartado == "comer" and ":" in contenido:
                    partes = contenido.split(":", 1)
                    candidato = partes[0].strip()
                    # Excluir encabezados genéricos al identificar restaurantes.
                    etiquetas_generales = ["menú", "menú del día", "carta", "precios",
                                           "precio", "horario", "platos", "bebidas"]
                    if (candidato.isupper() and len(candidato) <= 80
                            and candidato.lower() not in etiquetas_generales):
                        nombre = candidato
                        descripcion = partes[1].strip()
                        tipo = "Restaurante"

            if not tipo:
                tiene_nombre = False
                for separador in [" - ", " – ", " — "]:
                    if separador in contenido:
                        candidato, detalle = contenido.split(separador, 1)
                        if len(candidato) <= 120 and len(candidato.split()) <= 16:
                            nombre = candidato.strip()
                            descripcion = detalle.strip()
                            tiene_nombre = True
                        break
                if apartado == "hacer":
                    titulo = obtener_texto(etiqueta.find(["b", "strong"]))
                    if titulo and contenido.startswith(titulo):
                        nombre = titulo.rstrip(".:")
                        descripcion = contenido[len(titulo):].lstrip(" :.-") or contenido
                        tiene_nombre = True

                if tiene_nombre:
                    if apartado == "ver":
                        tipo = "Punto de interés"
                    elif apartado == "hacer":
                        tipo = "Actividad"
                    elif etiqueta.name == "li":
                        lista = etiqueta.find_parent(["ul", "ol"])
                        titulos_tipicos = ["platos típicos", "platos tradicionales", "postres",
                                           "bebidas típicas", "bebidas tradicionales"]
                        titulo_tipico = any(titulo in subapartado for titulo in titulos_tipicos)
                        if lista is lista_de_platos and (lista is not None or titulo_tipico):
                            tipo = tipo_de_lista
                        elif titulo_tipico:
                            if apartado == "comer" and "bebidas" not in subapartado:
                                tipo = "Plato típico"
                            else:
                                tipo = "Bebida típica"

            if not tipo:
                nombre = f"{subapartado or encabezado} ({numero})"
                descripcion = contenido
                tipo = "Información gastronómica"
                if apartado in ["ver", "hacer"]:
                    tipo = "Información de visitas"

            fila = crear_fila(ciudad, tipo, nombre.strip(), descripcion, fuente)
            if tipo not in ["Información gastronómica", "Información de visitas"]:
                for campo, etiquetas in ETIQUETAS_DATOS.items():
                    fila[campo] = buscar_dato(contenido, etiquetas)
                enlace = etiqueta.find("a", class_="external", href=True)
                if enlace is not None and enlace["href"].startswith(("http://", "https://", "//")):
                    fila["web"] = urljoin(fuente, enlace["href"])
            registros.append(fila)
    return registros


# Consulta a la API de Wikivoyage
def consultar_articulo(titulo):
    # None significa título inexistente. [] significa que no se extrajeron datos.
    parametros = {"action": "parse", "page": titulo, "prop": "text|revid",
                  "redirects": 1, "format": "json", "formatversion": 2,
                  "disableeditsection": 1}
    cabeceras = {"User-Agent": "ATD-Grupo7-Wikivoyage/1.0 (https://www.upv.es; uso academico)"}
    respuesta = requests.get(API, params=parametros, headers=cabeceras, timeout=25)
    respuesta.raise_for_status()
    datos = respuesta.json()
    if "error" in datos:
        if datos["error"].get("code") == "missingtitle":
            return None
        raise ValueError(datos["error"].get("info", "No se ha encontrado la ciudad."))
    if "parse" not in datos or not datos["parse"].get("text"):
        raise ValueError("La respuesta no contiene el texto de la ciudad.")

    articulo = datos["parse"]
    titulo = articulo.get("title", titulo)
    fuente = "https://es.wikivoyage.org/wiki/" + quote(titulo.replace(" ", "_"))
    # Enlazar la revisión exacta del artículo.
    if articulo.get("revid"):
        fuente = fuente + "?oldid=" + str(articulo["revid"])
    sopa = BeautifulSoup(articulo["text"], "html.parser")
    for elemento in sopa.select("script, style, .toc, #toc, .navbox, .metadata, .mw-editsection, .thumb"):
        elemento.decompose()
    fichas = extraer_fichas(sopa, titulo, fuente)
    textos = extraer_texto(sopa, titulo, fuente)
    return fichas + textos


# Integración con el planificador
def obtener_wikivoyage(ciudad_destino, pais_destino):
    """Devuelve una lista de diccionarios con los datos turísticos del destino."""
    ciudad_destino = ciudad_destino.strip()
    pais_destino = pais_destino.strip()
    if not ciudad_destino:
        raise ValueError("Escribe una ciudad de destino.")
    if not pais_destino:
        raise ValueError("Escribe un país de destino.")

    titulo = f"{ciudad_destino} ({pais_destino})"
    registros = consultar_articulo(titulo)
    if registros is None:
        # Si no existe «Ciudad (País)», probar solo la ciudad.
        registros = consultar_articulo(ciudad_destino)
    if registros is None:
        return []

    # Normalizar la clave de los duplicados y conservar el texto original.
    por_clave = {}
    for fila in registros:
        nombre = " ".join(fila["nombre"].lower().split())
        clave = (fila["ciudad"].lower(), fila["tipo"], nombre)
        if clave not in por_clave:
            por_clave[clave] = fila
        else:
            # Completar solo los campos vacíos del primer registro.
            guardada = por_clave[clave]
            for campo in COLUMNAS:
                if guardada[campo] == "":
                    guardada[campo] = fila[campo]
    for fila in por_clave.values():
        fila["tarifas"] = extraer_tarifas(fila["precio"])
    return list(por_clave.values())


# Salida por terminal
def mostrar_resultados(registros):
    grupos = {}
    for fila in registros:
        tipo = fila["tipo"]
        if tipo not in grupos:
            grupos[tipo] = []
        grupos[tipo].append(fila)

    print("\nDestino:", registros[0]["ciudad"])
    print("Total de registros:", len(registros))
    campos = {"descripcion": "Descripción", "direccion": "Dirección",
              "horario": "Horario", "precio": "Precio", "telefono": "Teléfono",
              "web": "Web"}
    for tipo, filas in grupos.items():
        print(f"\n{tipo} ({len(filas)})")
        for fila in filas:
            print("-", fila["nombre"])
            for campo, etiqueta in campos.items():
                if fila[campo]:
                    print(f"  {etiqueta}: {fila[campo]}")
    print("\nFuente:", registros[0]["fuente"])
    print("Los horarios y precios son orientativos, según la guía.")


def pedir_dato_obligatorio(pregunta):
    while True:
        dato = input(pregunta).strip()
        if dato:
            return dato


def main():
    print("WIKIVOYAGE - GRUPO 7")
    ciudad_destino = pedir_dato_obligatorio("Ciudad de destino: ")
    pais_destino = pedir_dato_obligatorio("País de destino: ")
    try:
        registros = obtener_wikivoyage(ciudad_destino, pais_destino)
    except (requests.RequestException, ValueError) as error:
        print("No se han podido obtener los datos:", error)
        return 1
    if not registros:
        print("No se han encontrado datos. Prueba con el título exacto de Wikivoyage.")
        return 1
    mostrar_resultados(registros)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

