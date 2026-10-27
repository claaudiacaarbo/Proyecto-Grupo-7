# -*- coding: utf-8 -*-


from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import requests


HOST = "booking-com15.p.rapidapi.com"
BASE_URL = f"https://{HOST}"

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
TIMEOUT = 45
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "resultados_booking_api"


class ApiError(RuntimeError):
    """Fallo controlado de la API."""


class BookingApi:
    def __init__(self, api_key: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": HOST,
                "Accept": "application/json",
                "User-Agent": "ATD-TravelProject/1.0",
            }
        )

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{BASE_URL}{path}"
        response = self.session.get(
            url,
            params=params,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        if response.status_code in {401, 403}:
            raise ApiError(
                f"HTTP {response.status_code}: revisa RAPIDAPI_KEY, "
                "la suscripcion y las condiciones de acceso."
            )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "desconocido")
            raise ApiError(
                f"HTTP 429: cuota o frecuencia excedida. "
                f"Reintentar despues de {retry_after}."
            )
        if not response.ok:
            detail = " ".join(response.text.split())[:700]
            raise ApiError(
                f"HTTP {response.status_code}: {detail}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiError("La respuesta no contiene JSON valido.") from exc

        if not isinstance(payload, dict):
            raise ApiError(
                f"Se esperaba un objeto JSON; llegó {type(payload).__name__}."
            )

        return payload


def walk_dicts(value: Any, path: str = "") -> Iterable[tuple[str, dict[str, Any]]]:
    """Recorre un JSON sin depender de todas las claves del proveedor."""
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            yield from walk_dicts(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_dicts(child, f"{path}[{index}]")


def walk_lists(
    value: Any, path: str = ""
) -> Iterable[tuple[str, list[Any]]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            if isinstance(child, list):
                yield child_path, child
            yield from walk_lists(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_lists(child, f"{path}[{index}]")


def first_matching_dict(
    payload: dict[str, Any],
    required_keys: tuple[str, ...],
    preferred_values: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    candidates = [
        record
        for _, record in walk_dicts(payload)
        if any(key in record for key in required_keys)
    ]
    if not candidates:
        raise ApiError(
            "No se encontro un objeto con las claves esperadas: "
            f"{required_keys}"
        )

    preferred_values = preferred_values or {}
    for key, accepted in preferred_values.items():
        for record in candidates:
            value = record.get(key)
            if (
                value is not None
                and str(value).casefold()
                in {item.casefold() for item in accepted}
            ):
                return record
    return candidates[0]


def find_results(
    payload: dict[str, Any],
    preferred_keywords: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Localiza la lista principal de ofertas dentro del JSON."""
    options: list[tuple[int, str, list[Any]]] = []
    for path, values in walk_lists(payload):
        dictionaries = [value for value in values if isinstance(value, dict)]
        if not dictionaries:
            continue
        folded_path = path.casefold()
        keyword_score = sum(
            10 for keyword in preferred_keywords
            if keyword.casefold() in folded_path
        )
        options.append((keyword_score + len(dictionaries), path, dictionaries))

    if not options:
        return []

    _, _, selected = max(options, key=lambda item: item[0])
    return selected


def scalar_values(
    value: Any,
    wanted_parts: tuple[str, ...],
    path: str = "",
    limit: int = 30,
) -> dict[str, Any]:
    """Extrae algunos campos legibles sin asumir un esquema fijo."""
    found: dict[str, Any] = {}
    if len(found) >= limit:
        return found
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            key_folded = key.casefold()
            if (
                isinstance(child, (str, int, float, bool))
                and any(part in key_folded for part in wanted_parts)
            ):
                found[child_path] = child
                if len(found) >= limit:
                    break
            else:
                found.update(
                    scalar_values(
                        child, wanted_parts, child_path, limit - len(found)
                    )
                )
            if len(found) >= limit:
                break
    elif isinstance(value, list):
        for index, child in enumerate(value[:5]):
            found.update(
                scalar_values(
                    child,
                    wanted_parts,
                    f"{path}[{index}]",
                    limit - len(found),
                )
            )
            if len(found) >= limit:
                break
    return found


def short_summary(record: dict[str, Any]) -> dict[str, Any]:
    fields = scalar_values(
        record,
        (
            "name",
            "title",
            "airline",
            "hotel",
            "property",
            "vehicle",
            "car",
            "price",
            "amount",
            "currency",
            "rating",
            "score",
            "duration",
            "supplier",
            "provider",
        ),
    )
    return fields


def search_flight_locations(
    api: BookingApi, airport_name: str
) -> dict[str, Any]:
    payload = api.get(
        "/api/v1/flights/searchDestination",
        {
            "query": airport_name,
            "languagecode": "en-us",
        },
    )
    location = first_matching_dict(
        payload,
        required_keys=("id",),
        preferred_values={
            "type": ("AIRPORT", "AIRPORT_CITY"),
            "name": (airport_name,),
        },
    )
    if "id" not in location:
        raise ApiError("La respuesta no incluia 'id' para el aeropuerto.")
    return location


def search_flight_offers(
    api: BookingApi,
    origin_id: str,
    destination_id: str,
    depart_date: str,
    return_date: str,
    adults: int,
) -> dict[str, Any]:
    return api.get(
        "/api/v1/flights/searchFlights",
        {
            "fromId": origin_id,
            "toId": destination_id,
            "departDate": depart_date,
            "returnDate": return_date,
            "stops": "none",
            "pageNo": 1,
            "adults": adults,
            "sort": "CHEAPEST",
            "cabinClass": "ECONOMY",
            "currency_code": "EUR",
        },
    )


def search_hotel_destination(
    api: BookingApi, city: str
) -> dict[str, Any]:
    payload = api.get(
        "/api/v1/hotels/searchDestination",
        {"query": city},
    )
    destination = first_matching_dict(
        payload,
        required_keys=("dest_id",),
        preferred_values={"search_type": ("CITY", "city")},
    )
    if "dest_id" not in destination:
        raise ApiError("La respuesta no incluia 'dest_id'.")
    return destination


def search_hotel_offers(
    api: BookingApi,
    destination: dict[str, Any],
    arrival_date: str,
    departure_date: str,
    adults: int,
) -> dict[str, Any]:
    return api.get(
        "/api/v1/hotels/searchHotels",
        {
            "dest_id": str(destination["dest_id"]),
            "search_type": str(
                destination.get("search_type")
                or destination.get("searchType")
                or "CITY"
            ).upper(),
            "arrival_date": arrival_date,
            "departure_date": departure_date,
            "adults": adults,
            "room_qty": 1,
            "page_number": 1,
            "units": "metric",
            "temperature_unit": "c",
            "languagecode": "en-us",
            "currency_code": "EUR",
            "location": "ES",
        },
    )


def search_car_destination(
    api: BookingApi, city: str, residence_country: str
) -> dict[str, Any]:
    payload = api.get(
        "/api/v2/cars/searchDestination",
        {
            "term": city,
            "countryOfResidence": residence_country.lower(),
        },
    )
    destination = first_matching_dict(
        payload,
        required_keys=("coordinates",),
    )
    coordinates = destination.get("coordinates")
    if not isinstance(coordinates, dict):
        raise ApiError("La ubicacion de coches no incluia coordenadas.")
    if "latitude" not in coordinates or "longitude" not in coordinates:
        raise ApiError("Faltan latitude/longitude en las coordenadas.")
    return destination


def search_car_offers(
    api: BookingApi,
    destination: dict[str, Any],
    pickup_date: str,
    dropoff_date: str,
    pickup_time: str,
    dropoff_time: str,
    residence_country: str,
) -> dict[str, Any]:
    coordinates = destination["coordinates"]
    location_name = str(
        destination.get("title")
        or destination.get("name")
        or destination.get("label")
        or "Roma"
    )
    return api.get(
        "/api/v2/cars/searchCarRentals",
        {
            "pick_up_latitude": coordinates["latitude"],
            "pick_up_longitude": coordinates["longitude"],
            "pick_up_date": pickup_date,
            "pick_up_time": pickup_time,
            "drop_off_date": dropoff_date,
            "drop_off_time": dropoff_time,
            "driver_age": 30,
            "pick_up_location_name": location_name,
            "drop_off_location_name": location_name,
            "countryOfResidence": residence_country.lower(),
        },
    )


def save_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_summary_csv(
    path: Path, sections: dict[str, list[dict[str, Any]]]
) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["categoria", "indice", "resumen"],
        )
        writer.writeheader()
        for category, records in sections.items():
            for index, record in enumerate(records, start=1):
                writer.writerow(
                    {
                        "categoria": category,
                        "indice": index,
                        "resumen": json.dumps(
                            short_summary(record),
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    }
                )


def validate_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "La fecha debe usar el formato YYYY-MM-DD."
        ) from exc
    if parsed < date.today():
        raise argparse.ArgumentTypeError("La fecha no puede ser pasada.")
    return parsed.isoformat()


def validate_time(value: str) -> str:
    try:
        return datetime.strptime(value, "%H:%M").strftime("%H:%M")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "La hora debe usar el formato HH:MM."
        ) from exc


def parse_args() -> argparse.Namespace:
    outbound_default = "2026-11-10"
    return_default = "2026-11-11"

    parser = argparse.ArgumentParser(
        description=(
            "Prueba REST para vuelos, alojamiento y coches "
            "entre Valencia y Roma."
        )
    )
    parser.add_argument(
        "--origin-airport-query",
        default="Valencia",
    )
    parser.add_argument(
        "--destination-airport-query",
        default="Rome",
    )
    parser.add_argument(
        "--destination-city",
        default="Rome",
    )
    parser.add_argument(
        "--outbound",
        type=validate_date,
        default=outbound_default,
    )
    parser.add_argument(
        "--return",
        dest="return_date",
        type=validate_date,
        default=return_default,
    )
    parser.add_argument("--adults", type=int, default=2)
    parser.add_argument(
        "--pickup-time",
        type=validate_time,
        default="10:00",
    )
    parser.add_argument(
        "--dropoff-time",
        type=validate_time,
        default="10:00",
    )
    parser.add_argument(
        "--country",
        default="ES",
        help="Codigo de pais para precios y pais de residencia.",
    )
    args = parser.parse_args()

    if args.return_date <= args.outbound:
        parser.error("--return debe ser posterior a --outbound.")
    if args.adults < 1:
        parser.error("--adults debe ser al menos 1.")
    if len(args.country) != 2:
        parser.error("--country debe ser un codigo ISO de dos letras.")

    return args


def _walk_scalars(
    value: Any, path: tuple[str, ...] = ()
) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = (*path, str(key))
            if isinstance(child, (str, int, float, bool)):
                yield child_path, child
            else:
                yield from _walk_scalars(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_scalars(child, (*path, str(index)))


def _first_value(value: Any, keys: tuple[str, ...]) -> Any | None:
    scalars = list(_walk_scalars(value))
    for wanted in keys:
        folded_wanted = wanted.casefold()
        for path, scalar in scalars:
            if str(path[-1]).casefold() == folded_wanted:
                return scalar
    return None


def _duration_text(value: Any) -> str:
    if isinstance(value, dict):
        segments = value.get("segments")
        if isinstance(segments, list):
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                total_time = segment.get("totalTime")
                if isinstance(total_time, (int, float)) and total_time > 0:
                    # Esta API expresa totalTime en segundos.
                    minutes = round(total_time / 60)
                    return f"{minutes // 60} h {minutes % 60:02d} min"

    duration = _first_value(
        value,
        (
            "duration",
            "durationMinutes",
            "flightDuration",
            "totalDuration",
        ),
    )
    if duration is None:
        return "No disponible"

    if isinstance(duration, (int, float)):
        minutes = int(duration)
        return f"{minutes // 60} h {minutes % 60} min"

    text = str(duration).strip()
    match = re.fullmatch(
        r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        days, hours, minutes = (
            int(part or 0) for part in match.groups()
        )
        hours += days * 24
        return f"{hours} h {minutes} min"
    if text.isdigit():
        minutes = int(text)
        return f"{minutes // 60} h {minutes % 60} min"
    return text


def _price_text(value: Any) -> str:
    candidates: list[tuple[int, str]] = []

    for path, mapping in walk_dicts(value):
        currency = mapping.get(
            "currencyCode",
            mapping.get("currency"),
        )
        amount: float | None = None

        units = mapping.get("units")
        if isinstance(units, (int, float)):
            nanos = mapping.get("nanos", 0)
            amount = float(units)
            if isinstance(nanos, (int, float)):
                amount += float(nanos) / 1_000_000_000
        else:
            raw_value = mapping.get(
                "value",
                mapping.get("amount"),
            )
            if isinstance(raw_value, dict):
                nested_units = raw_value.get("units")
                if isinstance(nested_units, (int, float)):
                    nanos = raw_value.get("nanos", 0)
                    amount = float(nested_units)
                    if isinstance(nanos, (int, float)):
                        amount += float(nanos) / 1_000_000_000
                    currency = raw_value.get(
                        "currencyCode",
                        raw_value.get("currency", currency),
                    )
            elif isinstance(raw_value, (int, float)):
                amount = float(raw_value)

        if amount is None:
            continue

        folded_path = path.casefold()
        score = 0
        if "total" in folded_path:
            score += 4
        if "grossprice" in folded_path:
            score += 3
        if "price" in folded_path:
            score += 2
        if "amount" in folded_path:
            score += 1

        currency_text = str(currency) if currency else ""
        price = f"{currency_text} {amount:.2f}".strip()
        candidates.append((score, price))

    if candidates:
        return max(candidates, key=lambda item: item[0])[1]
    return "No disponible"


def _first_name(
    value: Any, keys: tuple[str, ...]
) -> str:
    result = _first_value(value, keys)
    return str(result) if result is not None else "No disponible"


def main() -> int:
    api_key = RAPIDAPI_KEY.strip()
    if not api_key or api_key == "PEGA_AQUI_TU_CLAVE":
        print("Define la variable de entorno RAPIDAPI_KEY antes de ejecutar esta prueba.")
        return 2

    args = parse_args()
    api = BookingApi(api_key)

    try:
        origin_location = search_flight_locations(
            api, args.origin_airport_query
        )
        destination_location = search_flight_locations(
            api, args.destination_airport_query
        )

        flight_payload = search_flight_offers(
            api,
            origin_id=str(origin_location["id"]),
            destination_id=str(destination_location["id"]),
            depart_date=args.outbound,
            return_date=args.return_date,
            adults=args.adults,
        )
        flight_results = find_results(
            flight_payload,
            ("flightoffers", "itineraries", "offers", "results"),
        )
        if not flight_results:
            return 1
        flight = flight_results[0]

        hotel_location = search_hotel_destination(
            api, args.destination_city
        )
        hotel_payload = search_hotel_offers(
            api,
            hotel_location,
            arrival_date=args.outbound,
            departure_date=args.return_date,
            adults=args.adults,
        )
        hotel_results = find_results(
            hotel_payload,
            ("hotels", "properties", "results"),
        )
        if not hotel_results:
            return 1
        hotel = hotel_results[0]

        car_location = search_car_destination(
            api, args.destination_city, args.country
        )
        car_payload = search_car_offers(
            api,
            car_location,
            pickup_date=args.outbound,
            dropoff_date=args.return_date,
            pickup_time=args.pickup_time,
            dropoff_time=args.dropoff_time,
            residence_country=args.country,
        )
        car_results = find_results(
            car_payload,
            ("carrentals", "vehicles", "cars", "results"),
        )
        if not car_results:
            return 1
        car = car_results[0]
    except (ApiError, requests.RequestException):
        return 1

    print("VUELO")
    print(f"  Tiempo: {_duration_text(flight)}")
    print(f"  Precio: {_price_text(flight)}")
    print("ALOJAMIENTO")
    print(
        "  Nombre: "
        + _first_name(
            hotel,
            ("hotelName", "propertyName", "title", "name"),
        )
    )
    print(f"  Precio: {_price_text(hotel)}")
    print("COCHE")
    print(
        "  Coche: "
        + _first_name(
            car,
            ("vehicleName", "carName", "model", "name"),
        )
    )
    print(f"  Precio: {_price_text(car)}")

    return 0


if __name__ == "__main__":
    main()
