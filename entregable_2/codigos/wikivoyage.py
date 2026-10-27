# Grupo 7. Gastronomía y puntos de interés de Wikivoyage.
# Si faltan librerías, ejecutar en la terminal:
# python -m pip install requests beautifulsoup4

import csv
from pathlib import Path
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup


# 1. DATOS DEL EJEMPLO
# Roma aparece en el ejemplo de viaje de la propuesta del proyecto.
# Para otra ciudad, escribir su título tal como aparece en Wikivoyage.
CIUDAD = "Roma"
API = "https://es.wikivoyage.org/w/api.php"
COLUMNAS = ["ciudad", "tipo", "nombre", "descripcion", "direccion",
            "horario", "precio", "telefono", "web", "fuente"]
CARPETA = Path(__file__).resolve().parent / "resultados_wikivoyage"
ARCHIVO = CARPETA / "datos_wikivoyage.csv"


# 2. FUNCIONES PARA LEER Y ORGANIZAR LOS DATOS
def obtener_texto(etiqueta):
    if etiqueta is None:
        return ""
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
    fila = {}
    for columna in COLUMNAS:
        fila[columna] = ""
    fila["ciudad"] = ciudad
    fila["tipo"] = tipo
    fila["nombre"] = nombre
    fila["descripcion"] = descripcion
    fila["fuente"] = fuente
    return fila


def buscar_dato(texto, etiquetas):
    # Solo separamos un dato si el texto lo identifica con una etiqueta.
    for etiqueta in etiquetas:
        posicion = texto.lower().find(etiqueta)
        if posicion != -1:
            dato = texto[posicion + len(etiqueta):].strip()
            for otra_etiqueta in ["dirección:", "direccion:", "horario:", "horarios:",
                                  "precio medio por persona:", "precio medio:",
                                  "precio:", "teléfono:", "reservas:", "web:"]:
                final = dato.lower().find(otra_etiqueta)
                if final != -1:
                    dato = dato[:final].strip()
            return dato.split(". ", 1)[0]
    return ""


# 3. LEER LOS LUGARES QUE APARECEN EN FICHAS
def extraer_fichas(sopa, ciudad, fuente):
    registros = []
    tipos = {"ver": "Punto de interés", "see": "Punto de interés",
             "hacer": "Actividad", "do": "Actividad",
             "comer": "Restaurante", "eat": "Restaurante",
             "beber": "Bar o local de ocio", "drink": "Bar o local de ocio",
             "beber y salir": "Bar o local de ocio"}

    for ficha in sopa.find_all(class_=["voy-vCard", "vcard"]):
        # Evitamos fichas repetidas dentro de otras y menciones sueltas.
        if ficha.find_parent(class_=["voy-vCard", "vcard"]) is not None:
            continue
        if "voy-listing-inline" in ficha.get("class", []):
            continue
        # Hay alquileres de motos etiquetados como "see" en Cómo desplazarse.
        encabezado = obtener_texto(ficha.find_previous("h2")).lower()
        if encabezado not in ["ver", "hacer", "comer", "beber", "beber y salir"]:
            continue
        grupo = ficha.get("data-group", "").lower()
        tipo = tipos.get(grupo, "")
        if grupo == "":
            tipo = tipos.get(encabezado, "")
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


# 4. LEER LAS LISTAS Y PÁRRAFOS QUE NO TIENEN FICHA
def extraer_texto(sopa, ciudad, fuente):
    registros = []
    apartado = ""
    subapartado = ""
    lista_de_platos = None
    tipo_de_lista = "Plato típico"
    numero = 0
    for etiqueta in sopa.find_all(["h2", "h3", "h4", "p", "li"]):
        contenido = obtener_texto(etiqueta)
        if etiqueta.name == "h2":
            apartado = contenido.lower()
            subapartado = ""
            lista_de_platos = None
        elif etiqueta.name in ["h3", "h4"]:
            subapartado = contenido.lower()
            lista_de_platos = None
        elif apartado in ["ver", "hacer", "comer", "beber", "beber y salir"]:
            # Estas partes ya se han leído en extraer_fichas.
            if etiqueta.find_parent(class_=["voy-vCard", "vcard"]) is not None:
                continue
            if etiqueta.find(class_=["voy-vCard", "vcard"]) is not None:
                continue
            if "vcard" in etiqueta.get("class", []):
                continue
            if etiqueta.find_parent("li") is not None or contenido == "":
                continue
            if etiqueta.find_parent("figure") is not None:
                continue

            numero = numero + 1
            nombre = subapartado or apartado
            nombre = nombre + " (" + str(numero) + ")"
            descripcion = contenido
            tipo = "Información gastronómica"
            if apartado in ["ver", "hacer"]:
                tipo = "Información de visitas"

            # La frase introductoria solo afecta a la lista que viene justo después.
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
                # Algunos restaurantes están escritos como NOMBRE: explicación.
                if apartado == "comer" and ":" in contenido:
                    partes = contenido.split(":", 1)
                    candidato = partes[0].strip()
                    etiquetas_generales = ["menú", "menú del día", "carta", "precios",
                                           "precio", "horario", "platos", "bebidas"]
                    if (candidato.isupper() and len(candidato) <= 80
                            and candidato.lower() not in etiquetas_generales):
                        nombre = candidato
                        descripcion = partes[1].strip()
                        tipo = "Restaurante"

            if etiqueta.name in ["li", "p"] and tipo != "Restaurante":
                tiene_nombre = False
                for separador in [" - ", " – ", " — "]:
                    if separador in contenido:
                        candidato, detalle = contenido.split(separador, 1)
                        if len(candidato) <= 120 and len(candidato.split()) <= 16:
                            nombre = candidato.strip()
                            descripcion = detalle.strip()
                            tiene_nombre = True
                        break
                # En las actividades el título suele aparecer en negrita al inicio.
                negrita = etiqueta.find(["b", "strong"])
                titulo = obtener_texto(negrita)
                if apartado == "hacer" and titulo and contenido.startswith(titulo):
                    nombre = titulo.rstrip(".:")
                    descripcion = contenido[len(titulo):].lstrip(" :.-") or contenido
                    tiene_nombre = True

                es_lista_tipica = False
                if etiqueta.name == "li":
                    lista = etiqueta.find_parent(["ul", "ol"])
                    es_lista_tipica = lista_de_platos is not None and lista is lista_de_platos
                    for palabra in ["platos típicos", "platos tradicionales", "postres",
                                    "bebidas típicas", "bebidas tradicionales"]:
                        if palabra in subapartado:
                            es_lista_tipica = True
                if tiene_nombre:
                    if apartado == "ver":
                        tipo = "Punto de interés"
                    elif apartado == "hacer":
                        tipo = "Actividad"
                    elif es_lista_tipica:
                        tipo = "Plato típico"
                        if apartado != "comer" or "bebidas" in subapartado:
                            tipo = "Bebida típica"
                        if lista is lista_de_platos:
                            tipo = tipo_de_lista

                # Los párrafos y listas generales conservan un título de contexto.
                if tipo in ["Información gastronómica", "Información de visitas"]:
                    nombre = (subapartado or apartado) + " (" + str(numero) + ")"
                    descripcion = contenido

            fila = crear_fila(ciudad, tipo, nombre.strip(), descripcion, fuente)
            if tipo not in ["Información gastronómica", "Información de visitas"]:
                fila["direccion"] = buscar_dato(contenido, ["dirección:", "direccion:"])
                fila["precio"] = buscar_dato(contenido, ["precio medio por persona:",
                                                       "precio medio:", "precio:"])
                fila["horario"] = buscar_dato(contenido, ["horario:", "horarios:"])
                fila["telefono"] = buscar_dato(contenido, ["teléfono:"])
                enlace = etiqueta.find("a", class_="external", href=True)
                if enlace is not None and enlace["href"].startswith(("http://", "https://", "//")):
                    fila["web"] = urljoin(fuente, enlace["href"])
            registros.append(fila)
    return registros


# 5. CONSULTAR LA API DE WIKIVOYAGE
def consultar_ciudad(ciudad):
    parametros = {"action": "parse", "page": ciudad, "prop": "text|revid",
                  "redirects": 1, "format": "json", "formatversion": 2,
                  "disableeditsection": 1}
    cabeceras = {"User-Agent": "ATD-Grupo7-Wikivoyage/1.0 (https://www.upv.es; uso academico)"}
    respuesta = requests.get(API, params=parametros, headers=cabeceras, timeout=25)
    print("Código de respuesta de la API (HTTP):", respuesta.status_code)
    respuesta.raise_for_status()
    datos = respuesta.json()
    if "error" in datos:
        if datos["error"].get("code") == "missingtitle":
            raise ValueError("No existe un artículo para la ciudad: " + ciudad)
        raise ValueError(datos["error"].get("info", "No se ha encontrado la ciudad."))
    if "parse" not in datos or not datos["parse"].get("text"):
        raise ValueError("La respuesta no contiene el texto de la ciudad.")

    articulo = datos["parse"]
    titulo = articulo.get("title", ciudad)
    if titulo != ciudad:
        print("Artículo consultado:", titulo)
    fuente = "https://es.wikivoyage.org/wiki/" + quote(titulo.replace(" ", "_"))
    if articulo.get("revid"):
        fuente = fuente + "?oldid=" + str(articulo["revid"])
    sopa = BeautifulSoup(articulo["text"], "html.parser")
    for elemento in sopa.select("script, style, .toc, #toc, .navbox, .metadata, .mw-editsection, .thumb"):
        elemento.decompose()
    fichas = extraer_fichas(sopa, titulo, fuente)
    textos = extraer_texto(sopa, titulo, fuente)
    return fichas + textos


# 6. MOSTRAR LOS RESULTADOS Y GUARDARLOS EN UN CSV
def main():
    print("WIKIVOYAGE - GRUPO 7")
    print("Ciudad:", CIUDAD)
    try:
        registros = consultar_ciudad(CIUDAD)
    except (requests.RequestException, ValueError) as error:
        print("No se han podido obtener los datos:", error)
        print("Se conserva el CSV anterior, si existe.")
        return

    # Comparamos ciudad, tipo y nombre para no guardar el mismo dato dos veces.
    resultado = []
    claves = []
    for fila in registros:
        clave = (fila["ciudad"].casefold(), fila["tipo"], " ".join(fila["nombre"].casefold().split()))
        if clave not in claves:
            claves.append(clave)
            resultado.append(fila)
        else:
            guardada = resultado[claves.index(clave)]
            for campo in COLUMNAS:
                if guardada[campo] == "":
                    guardada[campo] = fila[campo]

    if len(resultado) == 0:
        print("No se han encontrado datos. Se conserva el CSV anterior.")
        return

    tipos = ["Plato típico", "Bebida típica", "Restaurante", "Bar o local de ocio",
             "Punto de interés", "Actividad", "Información gastronómica", "Información de visitas"]
    print("\nTotal de registros obtenidos (sin duplicados):", len(resultado))
    print("REGISTROS POR CATEGORÍA")
    for tipo in tipos:
        grupo = []
        for fila in resultado:
            if fila["tipo"] == tipo:
                grupo.append(fila)
        print(tipo + ":", len(grupo))

    print("\nEJEMPLOS REALES (uno por categoría principal)")
    for tipo in ["Punto de interés", "Restaurante", "Plato típico", "Bebida típica", "Actividad"]:
        ejemplo = None
        for fila in resultado:
            if fila["tipo"] == tipo:
                ejemplo = fila
                if fila["descripcion"]:
                    break
        if ejemplo is None:
            continue
        print("\n" + tipo + ": " + ejemplo["nombre"])
        descripcion = ejemplo["descripcion"]
        if len(descripcion) > 180:
            descripcion = descripcion[:177] + "..."
        print("  Descripción:", descripcion or "No disponible en el artículo.")
        for campo, titulo in [("direccion", "Dirección"), ("precio", "Precio"),
                              ("horario", "Horario"), ("fuente", "Fuente")]:
            if ejemplo[campo]:
                valor = ejemplo[campo]
                if campo != "fuente" and len(valor) > 180:
                    valor = valor[:177] + "..."
                print("  " + titulo + ":", valor)

    try:
        CARPETA.mkdir(exist_ok=True)
        with ARCHIVO.open("w", encoding="utf-8-sig", newline="") as fichero:
            escritor = csv.DictWriter(fichero, fieldnames=COLUMNAS, delimiter=";")
            escritor.writeheader()
            escritor.writerows(resultado)
    except PermissionError:
        print("\nNo se ha podido escribir el CSV.")
        print("Si está abierto en Excel, ciérralo y vuelve a ejecutar el programa.")
        return
    except OSError as error:
        print("\nNo se ha podido guardar el CSV:", error)
        return
    print("\nRegistros guardados:", len(resultado))
    print("CSV guardado en:", ARCHIVO)
    print("El CSV contiene todos los registros y los campos completos, sin recortes.")
    print("Los campos vacíos son datos que no se han podido extraer.")


if __name__ == "__main__":
    main()

# API utilizada: https://www.mediawiki.org/wiki/API:Parsing_wikitext
# Los precios se guardan como texto de la guía; no se actualizan por fecha de viaje.
