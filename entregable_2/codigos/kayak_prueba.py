# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import time
from typing import Any


URL = "https://www.kayak.es/flights/VLC-ROM/2026-11-10?sort=price_a"
PRICE_PATTERN = re.compile(
    r"(?:€|EUR|US\$|\$)\s?\d[\d.,]*"
    r"|\d[\d.,]*\s?(?:€|EUR)",
    re.IGNORECASE,
)
TIME_PATTERN = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b")
CHALLENGE_MARKERS = (
    "captcha",
    "verify you are human",
    "verify you are a human",
    "are you a robot",
    "unusual traffic",
    "access denied",
    "request blocked",
    "blocked",
    "forbidden",
)


def accept_cookies(driver: Any) -> bool:
    """Acepta solo un aviso normal de cookies si se encuentra."""
    selectors = (
        "#onetrust-accept-btn-handler",
        "button[data-test-id*='accept']",
        "button[data-testid*='accept']",
        "button[aria-label*='Aceptar']",
        "button[aria-label*='Accept']",
    )
    for selector in selectors:
        for button in driver.find_elements("css selector", selector):
            try:
                if button.is_displayed() and button.is_enabled():
                    button.click()
                    time.sleep(1)
                    return True
            except Exception:
                continue

    labels = {
        "aceptar",
        "aceptar todo",
        "aceptar todas",
        "accept",
        "accept all",
    }
    for button in driver.find_elements("tag name", "button")[:100]:
        try:
            label = " ".join(button.text.casefold().split())
            if button.is_displayed() and label in labels:
                button.click()
                time.sleep(1)
                return True
        except Exception:
            continue
    return False


def page_text(driver: Any) -> str:
    try:
        return driver.find_element("tag name", "body").text
    except Exception:
        return ""


def detect_barrier(text: str) -> str | None:
    folded = text.casefold()
    for marker in CHALLENGE_MARKERS:
        if marker in folded:
            return marker

    if len(" ".join(text.split())) < 120:
        return "pagina vacia o incompleta"
    return None


def wait_for_results_or_barrier(driver: Any, timeout: int = 35) -> str | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        text = page_text(driver)
        barrier = detect_barrier(text)
        if barrier:
            return barrier
        if PRICE_PATTERN.search(text):
            return None
        time.sleep(1)
    return "tiempo agotado sin precios visibles"


def get_one_flight(driver: Any) -> dict[str, str | None] | None:
    selectors = (
        "[data-resultid]",
        '[data-testid*="result"]',
        '[data-test-id*="result"]',
        '[role="link"]',
        "article",
    )
    seen: set[str] = set()

    for selector in selectors:
        for card in driver.find_elements("css selector", selector):
            try:
                if not card.is_displayed():
                    continue

                raw_text = card.text
                text = " ".join(raw_text.split())
                price_match = PRICE_PATTERN.search(text)
                if len(text) < 25 or not price_match or text in seen:
                    continue
                seen.add(text)

                time_match = TIME_PATTERN.search(text)
                flight_label = text[:500]

                for code in ("VLC", "ROM", "FCO", "CIA"):
                    if code in text.upper():
                        flight_label = (
                            f"Ruta con codigo {code} incluida en el resultado"
                        )
                        break

                link = None
                for anchor in card.find_elements(
                    "css selector", 'a[href^="http"]'
                ):
                    href = anchor.get_attribute("href")
                    if href:
                        link = href
                        break

                return {
                    "vuelo": flight_label,
                    "hora": time_match.group(0) if time_match else None,
                    "precio": price_match.group(0),
                    "enlace": link,
                    "texto": text[:3000],
                }
            except Exception:
                continue
    return None


def main() -> int:
    try:
        from selenium import webdriver
        from selenium.common.exceptions import WebDriverException
    except ImportError:
        print("Falta Selenium. Ejecuta: %pip install selenium")
        return 2

    options = webdriver.EdgeOptions()
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--lang=es-ES")

    driver = None
    try:
        driver = webdriver.Edge(options=options)
        driver.set_page_load_timeout(45)

        print("Prueba Kayak: Valencia (VLC) -> Roma (ROM)")
        print("Fecha: 2026-11-10")
        print(f"URL: {URL}\n")

        driver.get(URL)
        accepted = accept_cookies(driver)
        print(
            "Aviso de cookies: "
            + ("aceptado" if accepted else "no aparecio o no se pudo pulsar")
        )

        barrier = wait_for_results_or_barrier(driver)
        if barrier:
            print(f"\nBARRERA O FALLO: {barrier}")
            print(f"Titulo de pagina: {driver.title}")
            print(f"URL final: {driver.current_url}")
            visible = " ".join(page_text(driver).split())
            print(f"Texto inicial: {visible[:1000]}")
            return 1

        flight = get_one_flight(driver)
        if flight is None:
            print(
                "\nBARRERA O FALLO: habia precios en la pagina, "
                "pero no se pudo identificar una tarjeta de vuelo."
            )
            print(f"URL final: {driver.current_url}")
            return 1

        print("\nRESULTADO")
        print(f"VUELO: {flight['vuelo']}")
        print(f"HORA: {flight['hora']}")
        print(f"PRECIO: {flight['precio']}")
        print(f"ENLACE: {flight['enlace']}")
        return 0
    except WebDriverException as exc:
        print(f"\nError de Edge/WebDriver: {exc}")
        return 1
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
