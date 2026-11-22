# Grupo 7. Gastronomía y puntos de interés de Wikivoyage.
# Si faltan librerías, ejecutar en la terminal:
# python -m pip install requests beautifulsoup4

# Orden para estudiarlo: empieza por main() al final. Sigue con obtener_wikivoyage()
# y consultar_articulo(). Después mira cómo se extraen las fichas, el texto y las tarifas.
import re
# Decimal representa cantidades como 36,25 con precisión decimal para hacer cuentas.
from decimal import Decimal
# quote prepara caracteres como la ñ para una URL. urljoin completa enlaces relativos.
from urllib.parse import quote, urljoin

# requests pide el artículo a la API. BeautifulSoup permite recorrer el HTML recibido.
import requests
from bs4 import BeautifulSoup


# 1. CONFIGURACIÓN
# Esta URL es el punto al que enviamos las consultas de Wikivoyage en español.
API = "https://es.wikivoyage.org/w/api.php"
# Estas son las claves de cada ficha. Más adelante añadimos la lista tarifas.
COLUMNAS = ["ciudad", "tipo", "nombre", "descripcion", "direccion",
            "horario", "precio", "telefono", "web", "fuente"]
# Distintos títulos de la guía pueden significar lo mismo. Por ejemplo, «Lugares de interés» se trata como «Ver».
APARTADOS = {
    "ver": "ver", "lugares de interés": "ver",
    "hacer": "hacer",
    "comer": "comer", "comer y beber": "comer",
    "beber": "beber", "beber y salir": "beber", "vida nocturna": "beber",
}
# En el texto libre se reconocen datos escritos después de marcas como «Dirección:».
ETIQUETAS_DATOS = {
    "direccion": ["dirección:", "direccion:"],
    "horario": ["horario:", "horarios:"],
    "precio": ["precio medio por persona:", "precio medio:", "precio:"],
    "telefono": ["teléfono:"],
}
# El siguiente campo marca el fin del dato, aunque no lo guardemos.
LIMITES_DATOS = [
    etiqueta for variantes in ETIQUETAS_DATOS.values() for etiqueta in variantes
] + ["reservas:", "web:"]

# Los símbolos que se usan para varias monedas conservan un valor indeterminado.
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
# Invertimos la tabla anterior para buscar por símbolo o palabra y obtener el código.
# Por ejemplo, tanto «eur» como «€» y «euros» apuntan a «EUR».
MONEDAS = {
    forma.lower(): codigo
    for codigo, formas in ALIAS_MONEDAS.items()
    for forma in (codigo, *formas)
}
# Estos códigos se reconocen aunque no tengamos otros nombres para ellos.
for codigo in (
    "AED", "ARS", "CLP", "COP", "CRC", "CZK", "DKK", "EGP", "HKD", "HUF", "IDR",
    "ILS", "KRW", "MAD", "NOK", "NZD", "PEN", "PLN", "SEK", "SGD", "TRY", "TWD",
    "UYU", "ZAR",
):
    MONEDAS[codigo.lower()] = codigo
# Algunas marcas son ambiguas. Por ejemplo, si solo aparece $, se guarda None como moneda.
MONEDAS.update(dict.fromkeys(("$", "¥", "dólar", "dólares", "peso", "pesos")))

# Una expresión regular es un patrón para buscar texto. Aquí unimos las marcas con | (una u otra).
# re.escape hace que símbolos como $ se lean literalmente. Probamos antes US$ que $.
FORMAS_MONEDA = "|".join(re.escape(forma) for forma in sorted(MONEDAS, key=len, reverse=True))
# Los límites evitan reconocer un código de moneda en medio de una palabra.
# Si la marca va después del número, comprobamos que no introduzca otro importe.
MONEDA = rf"(?<![^\W\d_])(?:{FORMAS_MONEDA})(?![^\W\d_])"
MONEDA_SUFIJO = rf"{MONEDA}(?!\s*\d)"
# Los grupos de tres cifras son millares. La parte decimal tiene una o dos cifras.
# Se aceptan números como 1234, 1.234,50, 1,234.50 o 1 234,50.
# Las alternativas del patrón reflejan las distintas maneras de escribir miles y decimales.
NUMERO_PRECIO = (
    r"(?:\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?"
    r"|\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
    r"(?!\d|[.,]\d)"
)
# Buscamos un importe con la moneda antes o después. Puede seguirle un segundo importe.
# Por ejemplo, en «entre 10 y 20 €» guardamos 10 como importe y 20 como límite superior.
# Los nombres entre (?P<...>) sirven para recuperar cada parte. El patrón también busca «gratis».
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
# Buscamos dónde separar varias tarifas o suplementos. Una coma decimal como la de 36,25 se conserva.
SEPARADORES_TARIFA = re.compile(
    r"(?:[;!?]|,(?!\d)|\.(?=\s|$))(?![^()]*\))|\s+(?=(?:(?:más|plus)\b(?!\s+de\b)|\+\s))",
    re.IGNORECASE,
)
# Esta comprobación evita interpretar «no es gratis» como un precio de cero.
NEGACION_GRATUIDAD = re.compile(r"\b(?:no|not)(?:\s+(?:es|son|será|is|are))?\s+$", re.IGNORECASE)


# INICIO DEL BLOQUE CON APOYO DE IA (OpenAI Codex, GPT-6, apartado 4.3)
def convertir_importe(numero):
    # Quitamos los espacios para poder tratar igual «1 234,50» y «1234,50».
    numero = "".join(numero.split())
    # Si al final hay una coma o un punto seguido de una o dos cifras, lo tratamos como decimal.
    parte_decimal = re.search(r"[.,](\d{1,2})$", numero)
    if parte_decimal:
        # Quitamos los separadores de miles y construimos un valor como Decimal("1234.50").
        entero = re.sub(r"[.,]", "", numero[:parte_decimal.start()])
        return Decimal(f"{entero}.{parte_decimal[1]}")
    # Si el importe es entero, descartamos los separadores de miles y lo convertimos directamente.
    return Decimal(re.sub(r"[.,]", "", numero))


def identificar_moneda(marcas):
    # Devolvemos la primera marca que identifica una moneda concreta, como EUR.
    for marca in marcas:
        if MONEDAS[marca] is not None:
            return MONEDAS[marca]
    return None
# FIN DEL BLOQUE CON APOYO DE IA


def extraer_tarifas(precio):
    """Extrae importes orientativos y conserva las condiciones de la guía."""
    # Cada grupo guarda las posiciones de un fragmento y las tarifas encontradas en él.
    # Así podemos acompañar el importe de su condición, por ejemplo «para estudiantes».
    grupos = []
    inicio = 0
    # Cortamos el texto por los separadores. Añadimos la longitud total para leer el último fragmento.
    for fin in [m.start() for m in SEPARADORES_TARIFA.finditer(precio)] + [len(precio)]:
        fragmento = precio[inicio:fin]
        tarifas = []
        # finditer recorre todos los tramos que encajan con el patrón de precio.
        for coincidencia in PATRON_TARIFA.finditer(fragmento):
            if coincidencia["gratis"]:
                if NEGACION_GRATUIDAD.search(fragmento[:coincidencia.start()]):
                    continue
                # La gratuidad explícita se guarda como 0, sin moneda ni límite superior.
                tarifas.append((Decimal(0), None, None))
                continue

            # Recogemos la moneda que aparece junto a cada extremo del posible intervalo.
            marcas_inicio = [marca.lower() for marca in (coincidencia["moneda_antes"],
                                                        coincidencia["moneda_despues"]) if marca]
            marcas_fin = [marca.lower() for marca in (coincidencia["moneda_final_antes"],
                                                     coincidencia["moneda_final_despues"]) if marca]
            # Ignoramos números sin marca de moneda. Podrían ser una edad, una fecha o un horario.
            if not marcas_inicio and not marcas_fin:
                continue

            # Separamos las dos tareas. Primero identificamos la moneda y luego convertimos la cantidad.
            # Si solo hay un precio, hasta es None. En un intervalo, contiene el segundo importe.
            moneda_inicio = identificar_moneda(marcas_inicio)
            moneda_fin = identificar_moneda(marcas_fin)
            importe = convertir_importe(coincidencia["importe"])
            hasta = convertir_importe(coincidencia["hasta"]) if coincidencia["hasta"] else None
            if (marcas_inicio and marcas_fin
                    and (moneda_inicio or marcas_inicio[0]) != (moneda_fin or marcas_fin[0])):
                # Dos monedas distintas o sin equivalencia clara se guardan por separado.
                tarifas.extend([(importe, moneda_inicio, None), (hasta, moneda_fin, None)])
            else:
                tarifas.append((importe, moneda_inicio or moneda_fin, hasta))
        # Si el fragmento tiene importes, guardamos su posición. El primer grupo puede incluir texto previo.
        if tarifas:
            grupos.append((inicio if grupos else 0, fin, tarifas))
        elif grupos:
            # Un fragmento sin otro precio puede matizar la tarifa anterior.
            principio, _, anteriores = grupos[-1]
            grupos[-1] = (principio, fin, anteriores)
        inicio = fin + 1 if fin < len(precio) else fin

    # Convertimos cada tarifa en un diccionario y recuperamos el fragmento original como contexto.
    return [
        {"importe": importe, "moneda": moneda, "importe_hasta": hasta,
         "contexto": precio[inicio:fin].strip()}
        for inicio, fin, tarifas in grupos
        for importe, moneda, hasta in tarifas
    ]


# 2. FUNCIONES PARA LEER Y ORGANIZAR LOS DATOS
def obtener_texto(etiqueta):
    # BeautifulSoup devuelve None cuando no encuentra la etiqueta. En ese caso devolvemos texto vacío.
    if etiqueta is None:
        return ""
    # Extraemos el texto de la etiqueta y unimos sus palabras con un solo espacio.
    texto = etiqueta.get_text(" ", strip=True)
    return " ".join(texto.split())


def buscar_campo(ficha, clases):
    # Algunas fichas usan nombres de clase distintos para el mismo campo.
    for clase in clases:
        texto = obtener_texto(ficha.find(class_=clase))
        if texto != "":
            return texto
    return ""


def crear_fila(ciudad, tipo, nombre, descripcion, fuente):
    # Empezamos con todos los campos vacíos y rellenamos los que ya conocemos.
    fila = dict.fromkeys(COLUMNAS, "")
    fila["ciudad"] = ciudad
    fila["tipo"] = tipo
    fila["nombre"] = nombre
    fila["descripcion"] = descripcion
    fila["fuente"] = fuente
    return fila


def buscar_dato(texto, etiquetas):
    # Solo separamos un dato si el texto lo identifica con una etiqueta.
    # Buscamos las marcas en minúsculas, pero recortamos el texto original para conservar su escritura.
    texto_minusculas = texto.lower()
    for etiqueta in etiquetas:
        posicion = texto_minusculas.find(etiqueta)
        if posicion != -1:
            # Tomamos lo que viene después de la marca y paramos en el siguiente campo o al acabar la frase.
            dato = texto[posicion + len(etiqueta):].strip()
            for otra_etiqueta in LIMITES_DATOS:
                final = dato.lower().find(otra_etiqueta)
                if final != -1:
                    dato = dato[:final].strip()
            return dato.split(". ", 1)[0]
    return ""


# 3. LEER LOS LUGARES QUE APARECEN EN FICHAS
def extraer_fichas(sopa, ciudad, fuente):
    registros = []
    # Estas equivalencias traducen las categorías internas de las fichas a nombres que se muestran al usuario.
    tipos = {"ver": "Punto de interés", "see": "Punto de interés",
             "hacer": "Actividad", "do": "Actividad",
             "comer": "Restaurante", "eat": "Restaurante",
             "beber": "Bar o local de ocio", "drink": "Bar o local de ocio"}

    # find_all devuelve todas las etiquetas con una de las clases HTML que identifican fichas.
    for ficha in sopa.find_all(class_=["voy-vCard", "vcard"]):
        # Evitamos fichas repetidas dentro de otras y menciones sueltas.
        if ficha.find_parent(class_=["voy-vCard", "vcard"]) is not None:
            continue
        if "voy-listing-inline" in ficha.get("class", []):
            continue
        # Hay alquileres de motos etiquetados como "see" en Cómo desplazarse.
        encabezado = obtener_texto(ficha.find_previous("h2")).lower()
        apartado = APARTADOS.get(encabezado, "")
        if apartado == "":
            continue
        # data-group indica el tipo de ficha. Si falta, usamos el apartado en el que aparece.
        grupo = ficha.get("data-group", "").lower() or apartado
        tipo = tipos.get(grupo, "")
        nombre = buscar_campo(ficha, ["voy-listing-name", "listing-name", "fn"])
        if tipo == "" or nombre == "":
            continue

        # Creamos la ficha con la información básica y buscamos el resto de campos por sus clases HTML.
        descripcion = buscar_campo(ficha, ["voy-listing-content", "listing-content"])
        fila = crear_fila(ciudad, tipo, nombre, descripcion, fuente)
        fila["direccion"] = buscar_campo(ficha, ["voy-listing-address", "listing-address"])
        fila["horario"] = buscar_campo(ficha, ["voy-listing-hours", "listing-hours"])
        # Quitamos el icono del reloj para que el campo contenga el horario como texto.
        fila["horario"] = fila["horario"].replace("🕓", "").strip()
        fila["precio"] = buscar_campo(ficha, ["voy-listing-price", "listing-price"])
        # Quitamos la etiqueta «Precio:» y conservamos el texto con el importe y sus condiciones.
        if fila["precio"].startswith("Precio:"):
            fila["precio"] = fila["precio"][7:].strip()
        fila["telefono"] = buscar_campo(ficha, ["voy-listing-phone-number", "tel"])
        # Intentamos leer primero el enlace guardado en data-url y después el enlace externo del nombre.
        fila["web"] = ficha.get("data-url", "")
        if fila["web"] == "":
            enlace = ficha.find(class_=["voy-listing-name", "listing-name"])
            if enlace is not None:
                enlace = enlace.find("a", class_="external", href=True)
                if enlace is not None:
                    fila["web"] = enlace["href"]
        # Convertimos una ruta relativa en una dirección completa si hace falta.
        if fila["web"] != "":
            fila["web"] = urljoin(fuente, fila["web"])

        registros.append(fila)
    return registros


# 4. LEER LAS LISTAS Y PÁRRAFOS QUE NO TIENEN FICHA
def extraer_texto(sopa, ciudad, fuente):
    registros = []
    # Recordamos en qué apartado estamos mientras recorremos el artículo de arriba abajo.
    encabezado = ""
    apartado = ""
    subapartado = ""
    lista_de_platos = None
    tipo_de_lista = "Plato típico"
    numero = 0
    # h2, h3 y h4 son títulos. p significa párrafo y li indica un elemento de lista.
    for etiqueta in sopa.find_all(["h2", "h3", "h4", "p", "li"]):
        contenido = obtener_texto(etiqueta)
        # Un título principal cambia el apartado y reinicia la información del subapartado y de la lista.
        if etiqueta.name == "h2":
            encabezado = contenido.lower()
            apartado = APARTADOS.get(encabezado, "")
            subapartado = ""
            lista_de_platos = None
        elif etiqueta.name in ["h3", "h4"]:
            subapartado = contenido.lower()
            lista_de_platos = None
        # Solo procesamos párrafos y listas de los apartados incluidos en APARTADOS.
        elif apartado:
            # Estas partes ya se han leído en extraer_fichas.
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

            # La frase introductoria solo afecta a la lista que viene justo después.
            if etiqueta.name == "p":
                lista_de_platos = None
                for frase in ["puedes pedir", "platos típicos", "platos autóctonos",
                              "bebidas típicas", "bebidas tradicionales"]:
                    if frase in contenido.lower():
                        # find_next_sibling mira qué elemento viene justo después del párrafo.
                        # Si es una lista (ul u ol), la frase ayuda a decidir si contiene platos o bebidas.
                        siguiente = etiqueta.find_next_sibling()
                        if siguiente is not None and siguiente.name in ["ul", "ol"]:
                            lista_de_platos = siguiente
                            tipo_de_lista = "Plato típico"
                            if apartado != "comer" or "bebidas" in frase:
                                tipo_de_lista = "Bebida típica"
                # Algunos restaurantes están escritos como NOMBRE: explicación.
                if apartado == "comer" and ":" in contenido:
                    partes = contenido.split(":", 1)
                    candidato = partes[0].strip()
                    # Estas palabras pueden introducir información general y no se usan como nombres de restaurante.
                    etiquetas_generales = ["menú", "menú del día", "carta", "precios",
                                           "precio", "horario", "platos", "bebidas"]
                    if (candidato.isupper() and len(candidato) <= 80
                            and candidato.lower() not in etiquetas_generales):
                        nombre = candidato
                        descripcion = partes[1].strip()
                        tipo = "Restaurante"

            if not tipo:
                tiene_nombre = False
                # En un texto como «Museo — descripción», el guion separa el nombre del resto.
                for separador in [" - ", " – ", " — "]:
                    if separador in contenido:
                        candidato, detalle = contenido.split(separador, 1)
                        if len(candidato) <= 120 and len(candidato.split()) <= 16:
                            nombre = candidato.strip()
                            descripcion = detalle.strip()
                            tiene_nombre = True
                        break
                # En las actividades el título suele aparecer en negrita al inicio.
                if apartado == "hacer":
                    titulo = obtener_texto(etiqueta.find(["b", "strong"]))
                    if titulo and contenido.startswith(titulo):
                        nombre = titulo.rstrip(".:")
                        descripcion = contenido[len(titulo):].lstrip(" :.-") or contenido
                        tiene_nombre = True

                # Si se reconoce un nombre, el apartado o la lista determina cómo se clasifica.
                if tiene_nombre:
                    if apartado == "ver":
                        tipo = "Punto de interés"
                    elif apartado == "hacer":
                        tipo = "Actividad"
                    elif etiqueta.name == "li":
                        lista = etiqueta.find_parent(["ul", "ol"])
                        titulos_tipicos = ["platos típicos", "platos tradicionales", "postres",
                                           "bebidas típicas", "bebidas tradicionales"]
                        # El subtítulo también puede indicar que esa lista recoge platos o bebidas típicas.
                        titulo_tipico = any(titulo in subapartado for titulo in titulos_tipicos)
                        if lista is lista_de_platos and (lista is not None or titulo_tipico):
                            tipo = tipo_de_lista
                        elif titulo_tipico:
                            if apartado == "comer" and "bebidas" not in subapartado:
                                tipo = "Plato típico"
                            else:
                                tipo = "Bebida típica"

            # Si no encontramos un tipo concreto, guardamos el texto del apartado.
            if not tipo:
                # Para el texto general creamos un nombre a partir del apartado y el número del registro.
                nombre = f"{subapartado or encabezado} ({numero})"
                descripcion = contenido
                tipo = "Información gastronómica"
                if apartado in ["ver", "hacer"]:
                    tipo = "Información de visitas"

            fila = crear_fila(ciudad, tipo, nombre.strip(), descripcion, fuente)
            # Si identificamos un lugar o producto, buscamos sus datos concretos y su enlace cuando existen.
            if tipo not in ["Información gastronómica", "Información de visitas"]:
                for campo, etiquetas in ETIQUETAS_DATOS.items():
                    fila[campo] = buscar_dato(contenido, etiquetas)
                enlace = etiqueta.find("a", class_="external", href=True)
                if enlace is not None and enlace["href"].startswith(("http://", "https://", "//")):
                    fila["web"] = urljoin(fuente, enlace["href"])
            registros.append(fila)
    return registros


# 5. CONSULTAR LA API DE WIKIVOYAGE
def consultar_articulo(titulo):
    # None indica que no existe ese título. Una lista vacía indica que
    # el artículo existe, pero no contiene datos que podamos extraer.
    # La API recibe el título y devuelve el HTML del artículo y el número de su revisión en formato JSON.
    parametros = {"action": "parse", "page": titulo, "prop": "text|revid",
                  "redirects": 1, "format": "json", "formatversion": 2,
                  "disableeditsection": 1}
    # La cabecera identifica el proyecto. El límite de 25 segundos evita esperar indefinidamente.
    cabeceras = {"User-Agent": "ATD-Grupo7-Wikivoyage/1.0 (https://www.upv.es; uso academico)"}
    respuesta = requests.get(API, params=parametros, headers=cabeceras, timeout=25)
    # Primero comprobamos el estado HTTP y después convertimos el JSON en un diccionario de Python.
    respuesta.raise_for_status()
    datos = respuesta.json()
    # La API distingue entre un título inexistente y un error en la consulta.
    if "error" in datos:
        if datos["error"].get("code") == "missingtitle":
            return None
        raise ValueError(datos["error"].get("info", "No se ha encontrado la ciudad."))
    if "parse" not in datos or not datos["parse"].get("text"):
        raise ValueError("La respuesta no contiene el texto de la ciudad.")

    # Usamos el título que devuelve la API, que puede venir de una redirección.
    articulo = datos["parse"]
    titulo = articulo.get("title", titulo)
    fuente = "https://es.wikivoyage.org/wiki/" + quote(titulo.replace(" ", "_"))
    # El parámetro oldid enlaza exactamente la revisión que se leyó.
    if articulo.get("revid"):
        fuente = fuente + "?oldid=" + str(articulo["revid"])
    # BeautifulSoup transforma el HTML en elementos que podemos buscar y recorrer.
    sopa = BeautifulSoup(articulo["text"], "html.parser")
    # Retiramos el índice, la navegación y otros elementos que no aportan datos al listado.
    for elemento in sopa.select("script, style, .toc, #toc, .navbox, .metadata, .mw-editsection, .thumb"):
        elemento.decompose()
    # Leemos por separado los datos de fichas y el texto libre. El operador + junta ambas listas.
    fichas = extraer_fichas(sopa, titulo, fuente)
    textos = extraer_texto(sopa, titulo, fuente)
    return fichas + textos


# 6. FUNCIÓN PARA EL PROGRAMA DEL GRUPO
def obtener_wikivoyage(ciudad_destino, pais_destino):
    """Devuelve una lista de diccionarios con los datos turísticos del destino."""
    # Validamos aquí los datos también para cuando el programa del grupo llama sin usar la terminal.
    ciudad_destino = ciudad_destino.strip()
    pais_destino = pais_destino.strip()
    if not ciudad_destino:
        raise ValueError("Escribe una ciudad de destino.")
    # El país también es obligatorio aunque algunos artículos solo lleven el nombre de la ciudad.
    if not pais_destino:
        raise ValueError("Escribe un país de destino.")

    # En Wikivoyage hay títulos como Valencia (España) y Valencia (Venezuela).
    titulo = f"{ciudad_destino} ({pais_destino})"
    registros = consultar_articulo(titulo)
    if registros is None:
        # Si «Ciudad (País)» no existe, probamos únicamente el nombre de la ciudad.
        registros = consultar_articulo(ciudad_destino)
    if registros is None:
        return []

    # Comparamos ciudad, tipo y nombre para no guardar el mismo dato dos veces.
    # El diccionario usa como clave ciudad, tipo y nombre. Para comparar nombres, pasamos a minúsculas
    # y reducimos espacios. El texto que se muestra en la ficha mantiene su formato.
    por_clave = {}
    for fila in registros:
        nombre = " ".join(fila["nombre"].lower().split())
        clave = (fila["ciudad"].lower(), fila["tipo"], nombre)
        if clave not in por_clave:
            por_clave[clave] = fila
        else:
            # Si ya tenemos ese registro, completamos únicamente sus datos vacíos con la nueva ficha.
            guardada = por_clave[clave]
            for campo in COLUMNAS:
                if guardada[campo] == "":
                    guardada[campo] = fila[campo]
    # Con los duplicados ya resueltos, añadimos las tarifas calculables a partir de cada precio.
    for fila in por_clave.values():
        fila["tarifas"] = extraer_tarifas(fila["precio"])
    return list(por_clave.values())


# 7. MOSTRAR TODOS LOS RESULTADOS EN LA TERMINAL
def mostrar_resultados(registros):
    # Juntamos las fichas del mismo tipo para mostrarlas bajo un encabezado común.
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
    # Primero imprimimos la categoría y cuántos registros tiene. Después mostramos los campos disponibles.
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
    # input recoge lo que escribe el usuario. strip quita espacios de los extremos.
    # El bucle repite la pregunta hasta recibir algo y return devuelve ese dato.
    while True:
        dato = input(pregunta).strip()
        if dato:
            return dato


def main():
    # Este es el recorrido de la terminal. Recoge el destino, consulta la guía y muestra la salida.
    print("WIKIVOYAGE - GRUPO 7")
    ciudad_destino = pedir_dato_obligatorio("Ciudad de destino: ")
    pais_destino = pedir_dato_obligatorio("País de destino: ")
    try:
        registros = obtener_wikivoyage(ciudad_destino, pais_destino)
    # Si falla la conexión o la respuesta no es válida, mostramos el motivo y terminamos con error.
    except (requests.RequestException, ValueError) as error:
        print("No se han podido obtener los datos:", error)
        return 1
    # Una lista vacía indica que la búsqueda no devolvió datos para mostrar.
    if not registros:
        print("No se han encontrado datos. Prueba con el título exacto de Wikivoyage.")
        return 1
    mostrar_resultados(registros)
    return 0


# Este bloque llama a main() al ejecutar el archivo. Al importarlo desde el programa del grupo,
# las funciones quedan disponibles y el grupo puede pasarles los datos directamente.
if __name__ == "__main__":
    raise SystemExit(main())

# API utilizada: https://www.mediawiki.org/wiki/API:Parsing_wikitext
# Los precios se guardan como texto de la guía; no se actualizan por fecha de viaje.
