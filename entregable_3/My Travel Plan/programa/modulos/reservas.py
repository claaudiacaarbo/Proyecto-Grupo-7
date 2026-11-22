from __future__ import annotations

import re
import time
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import (
    urlencode,
)


PATRON_PRECIO = re.compile(
    r"(?:€|EUR)\s?\d[\d.,]*|\d[\d.,]*\s?(?:€|EUR)",
    re.IGNORECASE,
)
PATRON_TOTAL_COCHE = re.compile(
    r"Total for\s+\d+\s+days?\s*[:\-]?\s*"
    r"(?P<precio>(?:€|EUR)\s?\d[\d.,]*|\d[\d.,]*\s?(?:€|EUR))",
    re.IGNORECASE,
)
PATRON_VUELO = re.compile(
    r"(?P<hora>\d{1,2}:\d{2})\s*[–-]\s*"
    r"(?P<llegada>\d{1,2}:\d{2})(?P<desfase>\+\d+)?\s+"
    r"(?P<aerolinea>.+?)\s+"
    r"(?P<horas>\d+)\s*h(?:\s*(?P<minutos>\d+)\s*min)?",
    re.IGNORECASE,
)


# UTILIDADES COMUNES

def limpiar_texto(valor: Any) -> str:
    return " ".join(str(valor or "").split())


def detectar_verificacion_google(navegador: Any) -> bool:
    """Detecta la verificacion de trafico inusual sin intentar eludirla."""
    try:
        if "/sorry/" in navegador.current_url.casefold():
            return True
        cuerpo = normalizar_texto(
            navegador.find_element("tag name", "body").text
        )
    except Exception:
        return False

    mensajes = (
        "trafico inusual",
        "unusual traffic",
        "no soy un robot",
        "i am not a robot",
    )
    return any(mensaje in cuerpo for mensaje in mensajes)


def convertir_decimal(valor: Any) -> float:
    """Convierte precios europeos o anglosajones a un número decimal."""
    texto = limpiar_texto(valor).upper()
    texto = re.sub(r"[^0-9,.\-]", "", texto)
    if not texto:
        raise ValueError("No hay un numero que limpiar.")

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        partes = texto.split(",")
        # «2,080» y «1,234,567» agrupan millares; «2,08» es decimal.
        if len(partes) > 2 and all(len(parte) == 3 for parte in partes[1:]):
            texto = "".join(partes)
        elif len(partes[-1]) == 3:
            texto = "".join(partes)
        else:
            texto = "".join(partes[:-1]) + "." + partes[-1]
    elif "." in texto:
        # Google puede mostrar el precio en español como «2.080 €».
        # Sin esta comprobación se interpreta como 2,08 € en lugar de 2080 €.
        parte_entera, parte_final = texto.rsplit(".", 1)
        if texto.count(".") > 1 or len(parte_final) == 3:
            texto = texto.replace(".", "")
    return float(texto)


def formatear_euros(valor: float) -> str:
    return f"EUR {valor:.2f}"


def normalizar_texto(valor: Any) -> str:
    """Normaliza mayusculas y acentos para comparar textos de la pagina."""
    texto = unicodedata.normalize(
        "NFKD",
        limpiar_texto(valor).casefold(),
    )
    return "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )


from pathlib import Path

def abrir_edge() -> Any:
    from selenium import webdriver

    perfil = Path.home() / ".planificador-atd" / "perfil_edge"
    perfil.mkdir(parents=True, exist_ok=True)

    opciones = webdriver.EdgeOptions()
    opciones.add_argument(f"--user-data-dir={perfil}")
    opciones.add_argument("--window-size=1440,1000")
    opciones.add_argument("--lang=es-ES")
    navegador = webdriver.Edge(options=opciones)
    navegador.set_page_load_timeout(60)
    return navegador


def gestionar_aviso_privacidad(navegador: Any) -> None:
    selectores = (
        "#W0wltc",
        "#L2AGLb",
        "#onetrust-accept-btn-handler",
    )
    etiquetas = {
        "rechazar",
        "rechazar todo",
        "aceptar",
        "aceptar todo",
        "accept",
        "accept all",
    }
    fin = time.monotonic() + 10
    while time.monotonic() < fin:
        if detectar_verificacion_google(navegador):
            return

        for selector in selectores:
            for boton in navegador.find_elements("css selector", selector):
                try:
                    if boton.is_displayed() and boton.is_enabled():
                        boton.click()
                        time.sleep(1)
                        return
                except Exception:
                    continue

        for boton in navegador.find_elements("tag name", "button")[:100]:
            try:
                etiqueta = limpiar_texto(boton.text).casefold()
                if boton.is_displayed() and etiqueta in etiquetas:
                    boton.click()
                    time.sleep(1)
                    return
            except Exception:
                continue
        time.sleep(0.5)


# INICIO BLOQUE GENERADO CON IA
def obtener_bloques_precio_visibles(navegador: Any) -> list[str]:
    """Devuelve textos visibles con precio en el orden de la pagina."""
    codigo_javascript = r"""
    const selectors = [
      '[data-resultid]',
      'li',
      '[role="listitem"]',
      '[role="button"]',
      'article',
      '[class*="result"]',
      '[class*="card"]',
      'div'
    ];
    const nodes = new Set();
    for (const selector of selectors) {
      for (const node of document.querySelectorAll(selector)) nodes.add(node);
    }
    const found = [];
    const seen = new Set();
    for (const node of nodes) {
      const style = window.getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      if (style.display === 'none' || style.visibility === 'hidden' ||
          rect.width < 20 || rect.height < 10) continue;
      const text = (node.innerText || '').replace(/\s+/g, ' ').trim();
      if (text.length < 20 || text.length > 3000 || seen.has(text)) continue;
      if (!/(?:€|EUR)\s?\d[\d.,]*|\d[\d.,]*\s?(?:€|EUR)/i.test(text)) continue;
      seen.add(text);
      found.push({text, top: rect.top, left: rect.left});
    }
    found.sort((a, b) => (a.top - b.top) || (a.left - b.left));
    return found.map(item => item.text);
    """
    return navegador.execute_script(codigo_javascript)

# FIN BLOQUE GENERADO CON IA


def esperar_precios(navegador: Any, tiempo_espera: int = 45) -> bool:
    fin = time.monotonic() + tiempo_espera
    while time.monotonic() < fin:
        try:
            if PATRON_PRECIO.search(
                navegador.find_element("tag name", "body").text
            ):
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


# PARTE VUELOS

ESPERA_RESULTADOS_VUELO = 15


def buscar_vuelo(
    ciudad_origen: str,
    ciudad_destino: str,
    fecha_ida: str,
    fecha_vuelta: str,
    num_viajeros: int,
    hora_salida_ida_min: str | None = None,
    hora_salida_ida_max: str | None = None,
    hora_salida_vuelta_min: str | None = None,
    hora_salida_vuelta_max: str | None = None,
    cabina: str | None = None,
) -> dict[str, Any] | None:
    """Devuelve un vuelo de ida, uno de vuelta y sus precios limpios."""
    from selenium.common.exceptions import TimeoutException

    for intento in range(2):
        navegador = None
        try:
            navegador = abrir_edge()
            resultado_viaje = buscar_ida_vuelta(
                navegador,
                ciudad_origen,
                ciudad_destino,
                fecha_ida,
                fecha_vuelta,
                cabina,
                hora_salida_ida_min,
                hora_salida_ida_max,
                hora_salida_vuelta_min,
                hora_salida_vuelta_max,
            )
            if resultado_viaje is None:
                print("No existe resultado correspondiente")
                return None

            ida, vuelta, precio_persona = resultado_viaje

            precio_total = precio_persona * int(num_viajeros)
            ida.pop("duracion_minutos")
            vuelta.pop("duracion_minutos")
            return {
                "ida": ida,
                "vuelta": vuelta,
                "precio_persona": formatear_euros(precio_persona),
                "precio_total": formatear_euros(precio_total),
            }
        except TimeoutException:
            if intento == 0:
                print("Google Vuelos agotó el tiempo de espera. Reintentando…")
                continue
            print("Google Vuelos agotó el tiempo de espera tras dos intentos.")
            return None
        except Exception as error:
            print(f"Error interno al buscar vuelos: {type(error).__name__}: {error}")
            print("No existe resultado correspondiente")
            return None
        finally:
            if navegador is not None:
                try:
                    navegador.quit()
                except Exception:
                    pass


def convertir_hora_a_minutos(valor: str) -> int:
    analizado = datetime.strptime(valor.strip(), "%H:%M")
    return analizado.hour * 60 + analizado.minute


def navegar_antes_de(navegador: Any, fin: float, accion) -> bool:
    from selenium.common.exceptions import TimeoutException

    limite_anterior = navegador.timeouts.page_load
    tiempo_restante = fin - time.monotonic()
    if tiempo_restante <= 0:
        return False
    navegador.set_page_load_timeout(tiempo_restante)
    try:
        accion()
    except TimeoutException:
        return False
    finally:
        navegador.set_page_load_timeout(limite_anterior)
    return time.monotonic() < fin


def esperar_un_segundo(fin: float) -> None:
    time.sleep(min(1, max(0, fin - time.monotonic())))


def gestionar_error_temporal_google(
    navegador: Any, estado_recargas: list[int], fin: float
) -> bool:
    """Permite continuar si la página va bien o si aún se puede recargar."""
    try:
        texto = limpiar_texto(
            navegador.find_element("tag name", "body").text
        ).casefold()
    except Exception:
        return True

    errores_temporales = (
        "vaya, se ha producido un error",
        "vaya se ha producido un error",
        "something went wrong",
        "an error occurred",
    )
    if not any(mensaje in texto for mensaje in errores_temporales):
        return True
    if estado_recargas[0] or time.monotonic() >= fin:
        return False

    estado_recargas[0] = 1
    print("Google Vuelos ha dado un error. Volviendo a cargar una vez…", flush=True)
    for boton in navegador.find_elements("tag name", "button"):
        try:
            etiqueta = limpiar_texto(boton.text).casefold()
            visible = boton.is_displayed()
        except Exception:
            continue
        if visible and etiqueta in {"volver a cargar", "reload", "try again"}:
            recargado = navegar_antes_de(navegador, fin, boton.click)
            break
    else:
        recargado = navegar_antes_de(navegador, fin, navegador.refresh)

    if recargado:
        esperar_un_segundo(fin)
    return recargado and time.monotonic() < fin


def extraer_datos_vuelo(texto: str, fecha: str) -> dict[str, Any] | None:
    coincidencia = PATRON_VUELO.search(texto)
    if not coincidencia:
        return None

    aerolinea = re.split(
        r"\s*Operado por\s*|\s*Operated by\s*",
        coincidencia.group("aerolinea"),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    if not aerolinea:
        return None

    horas = int(coincidencia.group("horas"))
    minutos = int(coincidencia.group("minutos") or 0)
    precios = list(PATRON_PRECIO.finditer(texto))
    if not precios:
        return None
    precio = precios[-1]
    fecha_salida = datetime.strptime(fecha, "%Y-%m-%d")
    desplazamiento_dias = int(coincidencia.group("desfase") or "+0")
    fecha_llegada = fecha_salida + timedelta(days=desplazamiento_dias)
    return {
        "aerolinea": aerolinea,
        "salida": (
            f"{fecha_salida:%Y-%m-%d} "
            f"{coincidencia.group('hora').zfill(5)}"
        ),
        "llegada": (
            f"{fecha_llegada:%Y-%m-%d} "
            f"{coincidencia.group('llegada').zfill(5)}"
        ),
        "duracion": f"{horas} h {minutos:02d} min",
        "duracion_minutos": horas * 60 + minutos,
        "precio_persona": convertir_decimal(precio.group(0)),
    }


def cumple_filtro_horario_vuelo(
    vuelo: dict[str, Any],
    hora_min: str | None,
    hora_max: str | None,
) -> bool:
    minutos_salida = convertir_hora_a_minutos(vuelo["salida"][-5:])
    if hora_min is not None and minutos_salida < convertir_hora_a_minutos(hora_min):
        return False
    if hora_max is not None and minutos_salida > convertir_hora_a_minutos(hora_max):
        return False
    return True


def obtener_opciones_visibles(navegador: Any) -> list[Any]:
    opciones = []
    for elemento in navegador.find_elements(
        "css selector",
        '[role="option"]',
    ):
        try:
            if elemento.is_displayed() and limpiar_texto(elemento.text):
                opciones.append(elemento)
        except Exception:
            continue
    return opciones


def buscar_elemento_visible(
    navegador: Any,
    selector: str,
    predicado: Any,
    tiempo_espera: int = 20,
) -> Any | None:
    fin = time.monotonic() + tiempo_espera
    while time.monotonic() < fin:
        try:
            for elemento in navegador.find_elements("css selector", selector):
                if elemento.is_displayed() and predicado(elemento):
                    return elemento
        except Exception:
            pass
        time.sleep(0.25)
    return None


def buscar_elemento(
    navegador: Any,
    selector: str,
    predicado: Any,
    tiempo_espera: int = 10,
) -> Any | None:
    fin = time.monotonic() + tiempo_espera
    while time.monotonic() < fin:
        try:
            for elemento in navegador.find_elements("css selector", selector):
                try:
                    if predicado(elemento):
                        return elemento
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.25)
    return None


def obtener_selector_tipo_viaje(navegador: Any) -> Any | None:
    tipos_viaje = {
        "ida y vuelta",
        "solo ida",
        "varias ciudades",
    }

    def es_tipo_viaje(elemento: Any) -> bool:
        return normalizar_texto(elemento.text) in tipos_viaje

    return buscar_elemento_visible(
        navegador,
        'div[role="combobox"]',
        es_tipo_viaje,
    )


def seleccionar_tipo_viaje(navegador: Any, objetivo: str) -> bool:
    tipo_viaje = obtener_selector_tipo_viaje(navegador)
    if tipo_viaje is None:
        return False
    if normalizar_texto(tipo_viaje.text) == objetivo:
        return True

    tipo_viaje.click()
    opcion = buscar_elemento_visible(
        navegador,
        '[role="option"]',
        lambda elemento: normalizar_texto(elemento.text) == objetivo,
        tiempo_espera=10,
    )
    if opcion is None:
        return False
    opcion.click()
    time.sleep(1)
    return True


def obtener_campo_ubicacion(
    navegador: Any,
    parte: str,
    tiempo_espera: int = 20,
) -> Any | None:
    marcador = "desde" if parte == "origen" else "a donde"

    def coincide(elemento: Any) -> bool:
        etiquetas = (
            elemento.get_attribute("aria-label"),
            elemento.get_attribute("placeholder"),
        )
        return marcador in normalizar_texto(" ".join(str(valor or "") for valor in etiquetas))

    return buscar_elemento_visible(
        navegador,
        'input[role="combobox"]',
        coincide,
        tiempo_espera=tiempo_espera,
    )


def es_ciudad_valida(texto_opcion: str, ciudad: str) -> bool:
    normalizado = normalizar_texto(texto_opcion)
    marcadores_transporte = (
        "aeropuerto",
        "airport",
        "estacion",
        "station",
        "terminal",
        "helipuerto",
        "puerto",
        "port",
    )
    if any(marcador in normalizado for marcador in marcadores_transporte):
        return False
    if normalizado in {
        "cualquier lugar",
        "europa",
        "america",
        "asia",
        "africa",
        "oceania",
    }:
        return False

    solicitado = normalizar_texto(ciudad.split(",", 1)[0])
    sugerido = normalizar_texto(
        limpiar_texto(texto_opcion).split(",", 1)[0]
    )
    if not solicitado or not sugerido:
        return False
    return (
        sugerido == solicitado
        or sugerido.startswith(solicitado)
        or solicitado.startswith(sugerido)
    )

# INICIO BLOQUE GENERADO CON IA
def seleccionar_ciudad_google(
    navegador: Any,
    parte: str,
    ciudad: str,
) -> bool:
    campo = obtener_campo_ubicacion(navegador, parte)
    if campo is None:
        return False

    seleccionado = None
    for _ in range(2):
        navegador.execute_script(
            """
            const field = arguments[0];
            field.focus();
            field.value = arguments[1];
            field.dispatchEvent(new Event("input", {bubbles: true}));
            field.dispatchEvent(new Event("change", {bubbles: true}));
            """,
            campo,
            ciudad,
        )

        fin = time.monotonic() + 10
        while time.monotonic() < fin:
            for opcion in obtener_opciones_visibles(navegador):
                try:
                    valida = es_ciudad_valida(opcion.text, ciudad)
                except Exception:
                    continue
                # Google ordena las sugerencias por relevancia: elegir la
                # primera ciudad válida evita seleccionar una ciudad lejana
                # con el mismo nombre, como Madrid, Nuevo Mexico.
                if valida:
                    seleccionado = opcion
                    break
            if seleccionado is not None:
                break
            time.sleep(0.5)
        if seleccionado is not None:
            break
        campo = obtener_campo_ubicacion(navegador, parte)
        if campo is None:
            return False

    if seleccionado is None:
        return False
    try:
        seleccionado.click()
    except Exception:
        return False
    time.sleep(1)

    campo = obtener_campo_ubicacion(navegador, parte, tiempo_espera=10)
    return bool(campo and limpiar_texto(campo.get_attribute("value")))

# FIN BLOQUE GENERADO CON IA


def seleccionar_cabina(navegador: Any, cabina: str | None) -> bool:
    if not cabina:
        return True

    equivalencias = {
        "turista": "turista",
        "economica": "turista",
        "economy": "turista",
        "premium": "turista premium",
        "business": "business",
        "primera": "primera",
        "first": "primera",
    }
    objetivo = equivalencias.get(cabina.casefold())
    if objetivo is None:
        return True

    nombres_cabina = {
        "turista",
        "turista premium",
        "business",
        "primera",
    }

    def buscar_desplegable() -> Any | None:
        return buscar_elemento_visible(
            navegador,
            'div[role="combobox"]',
            lambda elemento: normalizar_texto(elemento.text) in nombres_cabina,
            tiempo_espera=10,
        )

    desplegable = buscar_desplegable()
    if desplegable is None:
        return False
    if normalizar_texto(desplegable.text) == objetivo:
        return True

    desplegable.click()
    opcion = buscar_elemento_visible(
        navegador,
        '[role="option"]',
        lambda elemento: normalizar_texto(elemento.text) == objetivo,
        tiempo_espera=10,
    )
    if opcion is None:
        return False
    opcion.click()
    time.sleep(0.5)
    return True


def confirmar_calendario(navegador: Any) -> bool:
    boton_hecho = buscar_elemento_visible(
        navegador,
        'button,[role="button"]',
        lambda elemento: normalizar_texto(elemento.text) == "hecho",
        tiempo_espera=10,
    )
    if boton_hecho is None:
        return False
    try:
        boton_hecho.click()
    except Exception:
        navegador.execute_script(
            "arguments[0].click();",
            boton_hecho,
        )
    time.sleep(1)
    return True


def seleccionar_fechas_google(
    navegador: Any,
    fecha_ida: str,
    fecha_vuelta: str,
) -> bool:
    """Selecciona ambas fechas sobre el calendario visible."""
    campos = [
        elemento
        for elemento in navegador.find_elements(
            "css selector", 'input[aria-label="Salida"]'
        )
        if elemento.is_displayed()
    ]
    if not campos:
        return False
    campos[0].click()
    time.sleep(1)

    for fecha_iso in (fecha_ida, fecha_vuelta):
        celda = buscar_elemento_visible(
            navegador,
            "[data-iso]",
            lambda elemento: (
                elemento.get_attribute("data-iso") == fecha_iso
            ),
            tiempo_espera=10,
        )
        if celda is None:
            return False
        celda.click()
        time.sleep(0.75)

    if not confirmar_calendario(navegador):
        return False

    valores = {}
    for elemento in navegador.find_elements("css selector", "input"):
        if not elemento.is_displayed():
            continue
        etiqueta = normalizar_texto(elemento.get_attribute("aria-label"))
        if etiqueta in {"salida", "vuelta"}:
            valores[etiqueta] = limpiar_texto(elemento.get_attribute("value"))
    return bool(valores.get("salida") and valores.get("vuelta"))


def enviar_busqueda_vuelo(navegador: Any, tiempo_espera: int = 20) -> bool:
    boton = buscar_elemento_visible(
        navegador,
        "button[aria-label]",
        lambda elemento: normalizar_texto(
            elemento.get_attribute("aria-label")
        )
        == "buscar",
        tiempo_espera=10,
    )
    if boton is None:
        return False

    try:
        boton.click()
    except Exception:
        # El calendario puede seguir abierto e interceptar el clic.
        navegador.execute_script("arguments[0].click();", boton)

    fin = time.monotonic() + tiempo_espera
    while time.monotonic() < fin:
        url_actual = navegador.current_url
        if (
            "/travel/flights/search" in url_actual
            or (
                "/travel/flights" in url_actual
                and "tfs=" in url_actual
            )
        ):
            return True
        time.sleep(0.5)
    return False


def abrir_todos_los_filtros(navegador: Any) -> bool:
    boton = buscar_elemento_visible(
        navegador,
        'button,[role="button"]',
        lambda elemento: "todos los filtros"
        in normalizar_texto(
            f"{elemento.text} "
            f"{elemento.get_attribute('aria-label') or ''}"
        ),
        tiempo_espera=20,
    )
    if boton is None:
        return False
    try:
        boton.click()
    except Exception:
        navegador.execute_script("arguments[0].click();", boton)
    return buscar_elemento_visible(
        navegador,
        '[role="tab"],button',
        lambda elemento: normalizar_texto(elemento.text) in {"ida", "vuelta"},
        tiempo_espera=10,
    ) is not None


# INICIO BLOQUE GENERADO CON IA
def ajustar_intervalo_hora(navegador: Any, etiqueta: str, hora: int) -> bool:
    campo = buscar_elemento(
        navegador,
        'input[type="range"]',
        lambda elemento: normalizar_texto(
            elemento.get_attribute("aria-label")
        )
        == normalizar_texto(etiqueta),
        tiempo_espera=10,
    )
    if campo is None:
        return False

    minimo = int(campo.get_attribute("min") or 0)
    maximo = int(campo.get_attribute("max") or 24)
    solicitado = max(minimo, min(maximo, hora))
    navegador.execute_script(
        """
        const field = arguments[0];
        const value = String(arguments[1]);
        const setter = Object.getOwnPropertyDescriptor(
          HTMLInputElement.prototype,
          "value"
        ).set;
        setter.call(field, value);
        field.dispatchEvent(new Event("input", {
          bubbles: true,
          composed: true
        }));
        field.dispatchEvent(new Event("change", {
          bubbles: true,
          composed: true
        }));
        field.blur();
        """,
        campo,
        solicitado,
    )
    time.sleep(0.75)

    campo = buscar_elemento(
        navegador,
        'input[type="range"]',
        lambda elemento: normalizar_texto(
            elemento.get_attribute("aria-label")
        )
        == normalizar_texto(etiqueta),
        tiempo_espera=5,
    )
    if campo is None:
        return False
    if int(campo.get_attribute("value") or -1) != solicitado:
        return False

    hora_mostrada = solicitado % 24
    texto_control = normalizar_texto(
        navegador.execute_script(
            "return arguments[0].parentElement.parentElement.innerText;",
            campo,
        )
    )
    return f"{hora_mostrada}:00" in texto_control

# FIN BLOQUE GENERADO CON IA


def aplicar_filtro_horario_direccion(
    navegador: Any,
    direccion: str,
    hora_minima: str | None,
    hora_maxima: str | None,
) -> bool:
    if hora_minima is None and hora_maxima is None:
        return True

    pestana = buscar_elemento_visible(
        navegador,
        '[role="tab"],button',
        lambda elemento: normalizar_texto(elemento.text)
        == normalizar_texto(direccion),
        tiempo_espera=10,
    )
    if pestana is None:
        return False
    pestana.click()
    time.sleep(0.5)

    if hora_minima is not None:
        hora_minima_salida = convertir_hora_a_minutos(hora_minima) // 60
        if not ajustar_intervalo_hora(
            navegador,
            "Salida más temprano",
            hora_minima_salida,
        ):
            return False

    if hora_maxima is not None:
        minuto_maximo = convertir_hora_a_minutos(hora_maxima)
        hora_maxima_salida = (minuto_maximo + 59) // 60
        hora_maxima_salida = min(24, hora_maxima_salida)
        if not ajustar_intervalo_hora(
            navegador,
            "Salida más tarde",
            hora_maxima_salida,
        ):
            return False
    return True


def cerrar_todos_los_filtros(navegador: Any) -> bool:
    control_filtros = buscar_elemento_visible(
        navegador,
        'button,[role="button"]',
        lambda elemento: "todos los filtros"
        in normalizar_texto(
            f"{elemento.text} "
            f"{elemento.get_attribute('aria-label') or ''}"
        ),
        tiempo_espera=5,
    )
    if control_filtros is not None:
        try:
            control_filtros.click()
        except Exception:
            navegador.execute_script("arguments[0].click();", control_filtros)

    fin = time.monotonic() + 5
    while time.monotonic() < fin:
        pestana_panel = buscar_elemento_visible(
            navegador,
            '[role="tab"],button',
            lambda elemento: normalizar_texto(elemento.text)
            in {"ida", "vuelta"},
            tiempo_espera=0.5,
        )
        if pestana_panel is None:
            time.sleep(1)
            return True
        time.sleep(0.5)

    cerrar = buscar_elemento_visible(
        navegador,
        'button,[role="button"]',
        lambda elemento: (
            normalizar_texto(elemento.text) == "cerrar"
            or normalizar_texto(
                elemento.get_attribute("aria-label")
            )
            == "cerrar"
        ),
        tiempo_espera=5,
    )
    if cerrar is not None:
        try:
            cerrar.click()
        except Exception:
            navegador.execute_script("arguments[0].click();", cerrar)
        time.sleep(1)
    return False


def aplicar_filtros_horarios_ida_vuelta(
    navegador: Any,
    hora_ida_min: str | None,
    hora_ida_max: str | None,
    hora_vuelta_min: str | None,
    hora_vuelta_max: str | None,
) -> bool:
    if (
        hora_ida_min is None
        and hora_ida_max is None
        and hora_vuelta_min is None
        and hora_vuelta_max is None
    ):
        return True

    if not abrir_todos_los_filtros(navegador):
        return False
    if not aplicar_filtro_horario_direccion(
        navegador,
        "Vuelta",
        hora_vuelta_min,
        hora_vuelta_max,
    ):
        return False
    if not aplicar_filtro_horario_direccion(
        navegador,
        "Ida",
        hora_ida_min,
        hora_ida_max,
    ):
        return False
    return cerrar_todos_los_filtros(navegador)


def preparar_busqueda_ida_vuelta(
    navegador: Any,
    ciudad_origen: str,
    ciudad_destino: str,
    fecha_ida: str,
    fecha_vuelta: str,
    cabina: str | None,
) -> bool:
    navegador.get(
        "https://www.google.com/travel/flights?hl=es&curr=EUR"
    )
    if detectar_verificacion_google(navegador):
        return False
    gestionar_aviso_privacidad(navegador)
    if detectar_verificacion_google(navegador):
        return False

    if not seleccionar_ciudad_google(navegador, "origen", ciudad_origen):
        print("No se pudo seleccionar el origen en Google Vuelos.")
        return False
    if not seleccionar_ciudad_google(navegador, "destino", ciudad_destino):
        print("No se pudo seleccionar el destino en Google Vuelos.")
        return False
    if obtener_selector_tipo_viaje(navegador) is None:
        print("Google Vuelos no mostró el selector del tipo de viaje.")
        return False
    if not seleccionar_tipo_viaje(navegador, "ida y vuelta"):
        print("No se pudo elegir ida y vuelta en Google Vuelos.")
        return False
    if not seleccionar_cabina(navegador, cabina):
        print("No se pudo elegir la cabina en Google Vuelos.")
        return False
    if not seleccionar_fechas_google(navegador, fecha_ida, fecha_vuelta):
        print("No se pudieron elegir las fechas en Google Vuelos.")
        return False
    if detectar_verificacion_google(navegador):
        return False

    if not enviar_busqueda_vuelo(navegador):
        print("No se pudo enviar el formulario de Google Vuelos.")
        return False
    # El calendario ya seleccionó las fechas; usar la URL que genera Google.
    # `tfs` es un parámetro interno opaco y no conviene reescribirlo a mano.
    url_actual = navegador.current_url
    correcta = (
        "/travel/flights/search" in url_actual
        or ("/travel/flights" in url_actual and "tfs=" in url_actual)
    )
    if not correcta:
        print(f"Google no abrió la página de resultados. URL: {url_actual}")
    return correcta


def esperar_precios_ida_vuelta(
    navegador: Any,
    tiempo_espera: int = ESPERA_RESULTADOS_VUELO,
    estado_recargas: list[int] | None = None,
) -> bool:
    if estado_recargas is None:
        estado_recargas = [0]
    fin = time.monotonic() + tiempo_espera
    while time.monotonic() < fin:
        if detectar_verificacion_google(navegador):
            return False
        if not gestionar_error_temporal_google(navegador, estado_recargas, fin):
            return False
        try:
            texto_cuerpo = navegador.find_element(
                "tag name",
                "body",
            ).text
        except Exception:
            texto_cuerpo = ""

        if PATRON_PRECIO.search(texto_cuerpo) and time.monotonic() < fin:
            return True
        esperar_un_segundo(fin)
    return False


# INICIO BLOQUE GENERADO CON IA
def obtener_candidatos_ida_vuelta(
    navegador: Any,
    fecha: str,
    hora_min: str | None,
    hora_max: str | None,
    fin: float = float("inf"),
) -> list[tuple[float, Any, dict[str, Any]]]:
    candidatos: dict[str, tuple[float, Any, dict[str, Any]]] = {}
    selectores = (
        "[data-resultid]",
        'li[role="listitem"]',
        '[role="listitem"]',
        "li",
    )

    for selector in selectores:
        if time.monotonic() >= fin:
            break
        for elemento in navegador.find_elements("css selector", selector):
            if time.monotonic() >= fin:
                break
            try:
                if not elemento.is_displayed():
                    continue
                texto = (
                    f"{elemento.text} "
                    f"{elemento.get_attribute('aria-label') or ''}"
                )
                if not PATRON_PRECIO.search(texto):
                    continue
                vuelo = extraer_datos_vuelo(texto, fecha)
                if not vuelo:
                    continue
                if not cumple_filtro_horario_vuelo(vuelo, hora_min, hora_max):
                    continue
                superficie = float(
                    navegador.execute_script(
                        "const r=arguments[0].getBoundingClientRect();"
                        "return Math.max(1, r.width * r.height);",
                        elemento,
                    )
                )
                actual = candidatos.get(elemento.id)
                if actual is None or superficie < actual[0]:
                    candidatos[elemento.id] = (superficie, elemento, vuelo)
            except Exception:
                continue

        if candidatos:
            break

    return sorted(
        candidatos.values(),
        key=lambda candidato: (
            float(candidato[2]["precio_persona"]),
            candidato[0],
        ),
    )

# FIN BLOQUE GENERADO CON IA


def seleccionar_candidato_ida_vuelta(
    navegador: Any,
    fecha: str,
    hora_min: str | None,
    hora_max: str | None,
    tiempo_espera: int = ESPERA_RESULTADOS_VUELO,
    estado_recargas: list[int] | None = None,
) -> tuple[Any, dict[str, Any]] | None:
    if estado_recargas is None:
        estado_recargas = [0]
    fin = time.monotonic() + tiempo_espera
    while time.monotonic() < fin:
        if detectar_verificacion_google(navegador):
            return None
        if not gestionar_error_temporal_google(navegador, estado_recargas, fin):
            return None
        candidatos = obtener_candidatos_ida_vuelta(
            navegador,
            fecha,
            hora_min,
            hora_max,
            fin,
        )
        if candidatos:
            _, elemento, vuelo = candidatos[0]
            try:
                pulsado = navegar_antes_de(navegador, fin, elemento.click)
            except Exception:
                pulsado = navegar_antes_de(
                    navegador, fin,
                    lambda: navegador.execute_script("arguments[0].click();", elemento),
                )
            return (elemento, vuelo) if pulsado else None
        esperar_un_segundo(fin)
    return None


def buscar_ida_vuelta(
    navegador: Any,
    ciudad_origen: str,
    ciudad_destino: str,
    fecha_ida: str,
    fecha_vuelta: str,
    cabina: str | None,
    hora_ida_min: str | None,
    hora_ida_max: str | None,
    hora_vuelta_min: str | None,
    hora_vuelta_max: str | None,
) -> tuple[dict[str, Any], dict[str, Any], float] | None:
    estado_recargas = [0]
    for intento in range(2):
        if not preparar_busqueda_ida_vuelta(
            navegador,
            ciudad_origen,
            ciudad_destino,
            fecha_ida,
            fecha_vuelta,
            cabina,
        ):
            if detectar_verificacion_google(navegador):
                return None
            if intento == 0:
                continue
            return None

        if not esperar_precios_ida_vuelta(
            navegador, estado_recargas=estado_recargas
        ):
            print("Google Vuelos no mostró precios tras esperar los resultados.")
            return None

        if not aplicar_filtros_horarios_ida_vuelta(
            navegador,
            hora_ida_min,
            hora_ida_max,
            hora_vuelta_min,
            hora_vuelta_max,
        ):
            if intento == 0:
                continue
            return None
        if not esperar_precios_ida_vuelta(
            navegador, estado_recargas=estado_recargas
        ):
            print("Google Vuelos dejó de mostrar resultados tras aplicar filtros.")
            return None

        seleccion_ida = seleccionar_candidato_ida_vuelta(
            navegador,
            fecha_ida,
            hora_ida_min,
            hora_ida_max,
            estado_recargas=estado_recargas,
        )
        if seleccion_ida is None:
            print("No se pudo identificar un vuelo de ida en los resultados.")
            return None

        time.sleep(2)
        seleccion_vuelta = seleccionar_candidato_ida_vuelta(
            navegador,
            fecha_vuelta,
            hora_vuelta_min,
            hora_vuelta_max,
            estado_recargas=estado_recargas,
        )
        if seleccion_vuelta is None:
            print("No se pudo identificar un vuelo de vuelta en los resultados.")
            return None

        _, vuelo_ida = seleccion_ida
        _, vuelo_vuelta = seleccion_vuelta
        precio_combinado = float(vuelo_vuelta["precio_persona"])
        vuelo_ida.pop("precio_persona", None)
        vuelo_vuelta.pop("precio_persona", None)
        return (
            vuelo_ida,
            vuelo_vuelta,
            precio_combinado,
        )
    return None


# PARTE ALOJAMIENTO

def buscar_alojamiento(
    ciudad_destino: str,
    fecha_ida: str,
    fecha_vuelta: str,
    num_viajeros: int,
    num_habitaciones: int | None = None,
    desayuno_incluido: bool | None = None,
    parking_gratis: bool | None = None,
) -> dict[str, Any] | None:
    """Devuelve un alojamiento y el precio total de las noches."""
    navegador = None
    try:
        fecha_entrada = datetime.strptime(fecha_ida, "%Y-%m-%d")
        fecha_salida_estancia = datetime.strptime(fecha_vuelta, "%Y-%m-%d")
        noches = (fecha_salida_estancia.date() - fecha_entrada.date()).days
        habitaciones = int(num_habitaciones or 1)

        meses = (
            "",
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        )
        consulta = (
            f"hoteles en {ciudad_destino} del "
            f"{fecha_entrada.day} de {meses[fecha_entrada.month]} de {fecha_entrada.year} al "
            f"{fecha_salida_estancia.day} de {meses[fecha_salida_estancia.month]} de "
            f"{fecha_salida_estancia.year} para {num_viajeros} adultos"
        )
        url = "https://www.google.com/travel/search?" + urlencode(
            {"q": consulta, "hl": "es", "curr": "EUR"}
        )

        navegador = abrir_edge()
        navegador.get(url)
        gestionar_aviso_privacidad(navegador)
        if not esperar_precios(navegador):
            print("No existe resultado correspondiente")
            return None

        marcadores_contenedor_filtros = (
            "todos los filtros",
            "ordenar por",
            "dónde alojarse",
            "cuándo ir",
            "importe que pagarás",
            "valoración de más",
            "menos de 50",
            "tipo de propiedad",
            "categoría del hotel",
        )
        for texto in obtener_bloques_precio_visibles(navegador):
            normalizado = texto.casefold()
            if "ver precios" not in normalizado:
                continue
            if any(
                marcador in normalizado
                for marcador in marcadores_contenedor_filtros
            ):
                continue
            if desayuno_incluido:
                desayuno_gratis = (
                    "desayuno gratis" in normalizado
                    or "free breakfast" in normalizado
                    or re.search(r"\bdesayuno\b(?!\s*\(\$)", normalizado)
                    is not None
                )
                if not desayuno_gratis:
                    continue
            if parking_gratis and not (
                "aparcamiento gratuito" in normalizado
                or "free parking" in normalizado
            ):
                continue

            coincidencia_precio = PATRON_PRECIO.search(texto)
            if not coincidencia_precio:
                continue
            precio_noche = convertir_decimal(coincidencia_precio.group(0))
            nombre = texto[:coincidencia_precio.start()]
            nombre = re.sub(
                r"^(?:Patrocinado\s*[·-]?\s*[^ ]+\s+hoteles\s+)",
                "",
                nombre,
                flags=re.IGNORECASE,
            )
            nombre = re.sub(
                r"\s*-\s*\d+\s+stars?\s*$",
                "",
                nombre,
                flags=re.IGNORECASE,
            )
            nombre = limpiar_texto(nombre).strip(" -|")
            if not nombre:
                continue

            return {
                "nombre": nombre,
                "precio_total": formatear_euros(
                    precio_noche * noches * habitaciones
                ),
            }

        print("No existe resultado correspondiente")
        return None
    except Exception:
        print("No existe resultado correspondiente")
        return None
    finally:
        if navegador is not None:
            try:
                navegador.quit()
            except Exception:
                pass


# PARTE COCHES

def buscar_coche(
    ciudad_destino: str,
    fecha_ida: str,
    fecha_vuelta: str,
    num_viajeros: int,
    num_asientos: int | None = None,
    transmision: str | None = None,
) -> dict[str, Any] | None:
    """Devuelve un coche y el precio total del periodo."""
    navegador = None
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        fecha_recogida = datetime.strptime(fecha_ida, "%Y-%m-%d").date()
        fecha_devolucion = datetime.strptime(fecha_vuelta, "%Y-%m-%d").date()
        min_asientos = int(num_asientos or num_viajeros)
        transmision = transmision.casefold() if transmision else None

        navegador = abrir_edge()
        navegador.get("https://www.discovercars.com/")
        gestionar_aviso_privacidad(navegador)

        campo_recogida = WebDriverWait(navegador, 20).until(
            lambda actual: actual.find_element(
                By.NAME, "PickupLocation"
            )
        )
        campo_recogida.clear()
        campo_recogida.send_keys(ciudad_destino)
        sugerencia = WebDriverWait(navegador, 20).until(
            lambda actual: actual.find_element(
                By.CSS_SELECTOR,
                ".Autocomplete-AutocompleteItem",
            )
        )
        sugerencia.click()

        navegador.find_elements(
            By.CSS_SELECTOR, ".DatePicker-DateWrapper"
        )[0].click()
        seleccionar_fecha_discovercars(navegador, fecha_recogida)
        seleccionar_fecha_discovercars(navegador, fecha_devolucion)

        boton_busqueda = WebDriverWait(navegador, 20).until(
            lambda actual: actual.find_element(
                By.CSS_SELECTOR, ".SearchModifier-SubmitBtn"
            )
        )
        boton_busqueda.click()
        if not esperar_precios(navegador, tiempo_espera=70):
            print("No existe resultado correspondiente")
            return None

        for texto in obtener_bloques_precio_visibles(navegador):
            normalizado = texto.casefold()
            if (
                "or similar" not in normalizado
                or "total for" not in normalizado
                or "view deal" not in normalizado
            ):
                continue

            asientos = re.search(r"(\d+)\s+seats?", normalizado)
            if not asientos or int(asientos.group(1)) < min_asientos:
                continue
            if transmision in {"automatica", "automática", "automatic"}:
                if "automatic" not in normalizado:
                    continue
            elif transmision == "manual" and "manual" not in normalizado:
                continue

            analizado = extraer_tarjeta_discovercars(texto)
            if analizado:
                nombre, precio = analizado
                return {
                    "nombre": nombre,
                    "precio_total": formatear_euros(precio),
                }

        print("No existe resultado correspondiente")
        return None
    except Exception:
        print("No existe resultado correspondiente")
        return None
    finally:
        if navegador is not None:
            try:
                navegador.quit()
            except Exception:
                pass


def seleccionar_fecha_discovercars(navegador: Any, solicitado: date) -> None:
    from selenium.webdriver.common.by import By

    objetivo = solicitado.strftime("%B %Y")
    for _ in range(36):
        encabezados = [
            limpiar_texto(elemento.text)
            for elemento in navegador.find_elements(
                By.CSS_SELECTOR, ".Calendar-NavigationMonth"
            )
            if elemento.is_displayed()
        ]
        if objetivo in encabezados:
            break
        if not encabezados:
            raise RuntimeError("Calendario no disponible.")
        analizado = [
            datetime.strptime(encabezado, "%B %Y")
            for encabezado in encabezados
            if encabezado
        ]
        if solicitado < analizado[0].date():
            flecha = navegador.find_element(
                By.CSS_SELECTOR, ".Calendar-ToPrevMonth"
            )
        else:
            flecha = navegador.find_element(
                By.CSS_SELECTOR, ".Calendar-ToNextMonth"
            )
        flecha.click()
        time.sleep(0.5)
    else:
        raise RuntimeError("No se pudo encontrar el mes.")

    encabezados = [
        limpiar_texto(elemento.text)
        for elemento in navegador.find_elements(
            By.CSS_SELECTOR, ".Calendar-NavigationMonth"
        )
        if elemento.is_displayed()
    ]
    indice = encabezados.index(objetivo)
    mes = navegador.find_elements(By.CSS_SELECTOR, ".rdrMonth")[indice]
    for boton_dia in mes.find_elements(By.CSS_SELECTOR, "button.rdrDay"):
        clases = boton_dia.get_attribute("class") or ""
        if (
            limpiar_texto(boton_dia.text) == str(solicitado.day)
            and "rdrDayPassive" not in clases
            and "rdrDayDisabled" not in clases
        ):
            boton_dia.click()
            time.sleep(1)
            return
    raise RuntimeError("No se pudo seleccionar el dia.")


def extraer_tarjeta_discovercars(texto: str) -> tuple[str, float] | None:
    coincidencia_total = PATRON_TOTAL_COCHE.search(texto)
    if not coincidencia_total:
        return None

    coincidencia_nombre = re.search(
        r"(?P<nombre>[\w .'’\-]{1,60}?)\s+or similar",
        texto,
        flags=re.IGNORECASE,
    )
    if not coincidencia_nombre:
        return None

    nombre = limpiar_texto(coincidencia_nombre.group("nombre"))
    nombre = re.sub(
        r"^(?:(?:No deposit|No deductible|Black Friday|"
        r"Free additional driver|"
        r"Excellent service|DiscoverCars choice)\s+)+",
        "",
        nombre,
        flags=re.IGNORECASE,
    )
    return nombre, convertir_decimal(coincidencia_total.group("precio"))
