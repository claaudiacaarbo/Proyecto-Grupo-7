# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import time
from typing import Any


URL = (
    "https://www.google.com/travel/search"
    "?q=hotels%20in%20Rome%20from%202026-11-10"
    "%20to%202026-11-11%20for%201%20adult"
    "&checkin=2026-11-10&checkout=2026-11-11"
    "&hl=es&curr=EUR"
)
PRICE = re.compile(
    r"(?:€|EUR|US\$|\$)\s?\d[\d.,]*"
    r"|\d[\d.,]*\s?(?:€|EUR)",
    re.IGNORECASE,
)


def accept_consent(driver: Any) -> None:
    labels = {
        "rechazar todo",
        "rechazar",
        "aceptar todo",
        "aceptar",
        "reject all",
        "accept all",
    }
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        for selector in ("#W0wltc", "#L2AGLb"):
            for button in driver.find_elements("css selector", selector):
                try:
                    if button.is_displayed():
                        button.click()
                        time.sleep(1)
                        return
                except Exception:
                    continue

        for button in driver.find_elements("tag name", "button")[:80]:
            try:
                if (
                    button.is_displayed()
                    and " ".join(button.text.casefold().split()) in labels
                ):
                    button.click()
                    time.sleep(1)
                    return
            except Exception:
                continue
        time.sleep(0.5)


def has_challenge(driver: Any) -> bool:
    try:
        text = driver.find_element("tag name", "body").text.casefold()
    except Exception:
        return False
    return any(
        marker in text
        for marker in (
            "captcha",
            "verify you are human",
            "are you a robot",
            "unusual traffic",
            "access denied",
        )
    )


def wait_for_result(driver: Any, seconds: int = 40) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            text = driver.find_element("tag name", "body").text
            if PRICE.search(text) and any(
                word in text.casefold()
                for word in ("hotel", "alojamiento", "noche")
            ):
                return True
        except Exception:
            pass
        if has_challenge(driver):
            return False
        time.sleep(1)
    return False


def first_hotel(driver: Any) -> str | None:
    script = r"""
    const nodes = new Set();
    for (const selector of [
      'li', '[role="listitem"]', '[role="button"]', 'article', 'div'
    ]) {
      for (const node of document.querySelectorAll(selector)) nodes.add(node);
    }
    const found = [];
    for (const node of nodes) {
      const style = window.getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      if (style.display === 'none' || style.visibility === 'hidden' ||
          rect.width < 20 || rect.height < 10) continue;
      const text = (node.innerText || '').replace(/\s+/g, ' ').trim();
      if (text.length < 30 || text.length > 1800) continue;
      if (!/(?:€|EUR|US\$|\$)|\d[\d.,]*\s?€/i.test(text)) continue;
      if (!/(hotel|alojamiento|noche|ver precios)/i.test(text)) continue;
      found.push(text);
    }
    found.sort((a, b) => a.length - b.length);
    return found.length ? found[0] : null;
    """
    return driver.execute_script(script)


def main() -> int:
    try:
        from selenium import webdriver
        from selenium.common.exceptions import WebDriverException
    except ImportError:
        print("Falta Selenium.")
        return 2

    options = webdriver.EdgeOptions()
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--lang=es-ES")

    driver = None
    try:
        driver = webdriver.Edge(options=options)
        driver.set_page_load_timeout(45)
        driver.get(URL)
        accept_consent(driver)

        if not wait_for_result(driver):
            if has_challenge(driver):
                print("Google ha mostrado un captcha.")
            else:
                print("No se encontro alojamiento con precio.")
            return 1

        result = first_hotel(driver)
        if not result:
            print("No se pudo leer el alojamiento.")
            return 1

        print("ALOJAMIENTO")
        print(result)
        price = PRICE.search(result)
        if price:
            print(f"Precio: {price.group(0)}")
        return 0
    except WebDriverException as exc:
        print(f"Error de Edge: {exc}")
        return 1
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
