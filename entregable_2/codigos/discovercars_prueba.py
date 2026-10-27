# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import time
from typing import Any


HOME_URL = "https://www.discovercars.com/"
PRICE = re.compile(
    r"(?:€|EUR)\s?\d[\d.,]*|\d[\d.,]*\s?(?:€|EUR)",
    re.IGNORECASE,
)


def accept_cookies(driver: Any) -> None:
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        for button in driver.find_elements(
            "css selector", "#onetrust-accept-btn-handler"
        ):
            try:
                if button.is_displayed() and button.is_enabled():
                    button.click()
                    time.sleep(1)
                    return
            except Exception:
                continue
        time.sleep(0.5)


def fill_search(driver: Any) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    pickup = WebDriverWait(driver, 20).until(
        lambda current: current.find_element(
            By.NAME, "PickupLocation"
        )
    )
    pickup.clear()
    pickup.send_keys("Rome")

    suggestion = WebDriverWait(driver, 20).until(
        lambda current: current.find_element(
            By.XPATH,
            (
                "//div[contains(@class,'Autocomplete-AutocompleteItem')]"
                "[contains(.,'Rome (all locations)')]"
            ),
        )
    )
    suggestion.click()

    first_date = WebDriverWait(driver, 20).until(
        lambda current: current.find_elements(
            By.CSS_SELECTOR, ".DatePicker-DateWrapper"
        )[0]
    )
    first_date.click()

    day_10 = WebDriverWait(driver, 20).until(
        lambda current: current.find_element(
            By.XPATH,
            (
                "//button[normalize-space(.)='10' "
                "and not(contains(@class,'rdrDayDisabled'))]"
            ),
        )
    )
    day_10.click()
    time.sleep(1)

    day_11 = WebDriverWait(driver, 20).until(
        lambda current: current.find_element(
            By.XPATH,
            (
                "//button[normalize-space(.)='11' "
                "and not(contains(@class,'rdrDayDisabled'))]"
            ),
        )
    )
    day_11.click()
    time.sleep(1)

    search = WebDriverWait(driver, 20).until(
        lambda current: current.find_element(
            "css selector", ".SearchModifier-SubmitBtn"
        )
    )
    search.click()


def first_car(driver: Any) -> str | None:
    selectors = (
        '[class*="SearchResult"]',
        '[class*="CarResult"]',
        '[class*="Offer"]',
        "article",
        "li",
        "div",
    )
    seen: set[str] = set()
    candidates: list[str] = []

    for selector in selectors:
        for node in driver.find_elements("css selector", selector):
            try:
                if not node.is_displayed():
                    continue
                text = " ".join(node.text.split())
                if len(text) < 30 or len(text) > 1800:
                    continue
                if not PRICE.search(text):
                    continue
                if "total for" not in text.casefold():
                    continue
                if "view deal" not in text.casefold():
                    continue
                if "or similar" not in text.casefold():
                    continue
                if text in seen:
                    continue
                seen.add(text)
                candidates.append(text)
            except Exception:
                continue

    if not candidates:
        return None
    candidates.sort(key=len)
    return candidates[0]


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
        driver.get(HOME_URL)
        accept_cookies(driver)
        fill_search(driver)

        deadline = time.monotonic() + 60
        result = None
        while time.monotonic() < deadline:
            result = first_car(driver)
            if result:
                break
            time.sleep(1)

        if result is None:
            print("DiscoverCars no devolvio un coche con precio.")
            return 1

        print("COCHE")
        print(result)
        price = PRICE.search(result)
        if price:
            print(f"Precio: {price.group(0)}")
        return 0
    except WebDriverException as exc:
        print(f"Error de Edge: {exc}")
        return 1
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}")
        return 1
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
