# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import time
from typing import Any


URL = (
    "https://www.google.com/travel/flights"
    "?q=Flights%20from%20Valencia%20to%20Rome"
    "%20on%202026-11-10%20one%20way"
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
            if PRICE.search(text) and re.search(r"\b\d{1,2}:\d{2}\b", text):
                return True
        except Exception:
            pass
        if has_challenge(driver):
            return False
        time.sleep(1)
    return False


def first_flight(driver: Any) -> str | None:
    script = r"""
    const nodes = new Set();
    for (const selector of [
      'li', '[role="listitem"]', '[role="button"]', 'article'
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
      if (text.length < 25 || text.length > 1800) continue;
      if (!/(?:€|EUR|US\$|\$)|\d[\d.,]*\s?€/i.test(text)) continue;
      if (!/\b\d{1,2}:\d{2}\b/.test(text)) continue;
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
                print("No se encontro un vuelo con hora y precio.")
            return 1

        result = first_flight(driver)
        if not result:
            print("No se pudo leer el vuelo.")
            return 1

        print("VUELO")
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
