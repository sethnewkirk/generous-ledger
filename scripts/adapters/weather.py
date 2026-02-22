#!/usr/bin/env python3
"""
weather.py — Fetch weather data from Open-Meteo and write to vault.

USAGE:
    python3 scripts/adapters/weather.py [--vault PATH] [--lat LAT] [--lon LON] [--days N]

Open-Meteo is free with no API key required.
Default location is Washington, DC (user's city based on profile).

EXAMPLES:
    python3 scripts/adapters/weather.py
    python3 scripts/adapters/weather.py --vault ~/Documents/Achaean
    python3 scripts/adapters/weather.py --lat 38.9072 --lon -77.0369 --days 3
"""

import argparse
import sys
import json
from datetime import date, datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

# Add parent to path for lib imports
sys.path.append(str(Path(__file__).parent))

from lib.vault_writer import VaultWriter
from lib.sync_state import SyncState
from lib.logging_config import setup_logging
from lib.credentials import get_config

# Weather code descriptions (WMO codes)
WMO_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}

# Simplified condition categories for frontmatter
def simplify_condition(code: int) -> str:
    if code <= 1:
        return "clear"
    elif code <= 3:
        return "partly-cloudy" if code == 2 else "overcast"
    elif code <= 48:
        return "fog"
    elif code <= 57:
        return "drizzle"
    elif code <= 67:
        return "rain"
    elif code <= 77:
        return "snow"
    elif code <= 82:
        return "rain-showers"
    elif code <= 86:
        return "snow-showers"
    else:
        return "thunderstorm"


def fetch_weather(lat: float, lon: float, days: int = 3) -> dict:
    """Fetch weather forecast from Open-Meteo API.

    Args:
        lat: Latitude
        lon: Longitude
        days: Number of forecast days (1-16)

    Returns:
        API response dict.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        f"precipitation_probability_max,sunrise,sunset,wind_speed_10m_max"
        f"&temperature_unit=fahrenheit"
        f"&wind_speed_unit=mph"
        f"&timezone=auto"
        f"&forecast_days={days}"
    )

    req = Request(url, headers={"User-Agent": "generous-ledger/1.0"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def format_day(daily: dict, idx: int) -> tuple[dict, str]:
    """Format a single day's weather into frontmatter and body.

    Args:
        daily: The 'daily' object from Open-Meteo response.
        idx: Index into the daily arrays.

    Returns:
        Tuple of (frontmatter_dict, body_string).
    """
    date_str = daily["time"][idx]
    code = daily["weather_code"][idx]
    high = round(daily["temperature_2m_max"][idx])
    low = round(daily["temperature_2m_min"][idx])
    precip = daily["precipitation_probability_max"][idx]
    sunrise = daily["sunrise"][idx].split("T")[1][:5] if daily["sunrise"][idx] else ""
    sunset = daily["sunset"][idx].split("T")[1][:5] if daily["sunset"][idx] else ""
    wind = round(daily["wind_speed_10m_max"][idx])

    condition = simplify_condition(code)
    description = WMO_CODES.get(code, "unknown")

    frontmatter = {
        "type": "weather-daily",
        "date": date_str,
        "high_f": high,
        "low_f": low,
        "condition": condition,
        "precipitation_chance": precip,
        "wind_max_mph": wind,
        "sunrise": sunrise,
        "sunset": sunset,
        "wmo_code": code,
        "source": "open-meteo",
        "tags": ["data", "weather"],
    }

    body_lines = [
        f"# Weather — {date_str}",
        "",
        f"**{description.title()}**. High of {high}°F, low of {low}°F.",
        "",
    ]

    if precip > 0:
        body_lines.append(f"Precipitation chance: {precip}%.")
    if wind > 15:
        body_lines.append(f"Windy — gusts up to {wind} mph.")

    body_lines.extend([
        "",
        f"Sunrise {sunrise}, sunset {sunset}.",
    ])

    return frontmatter, "\n".join(body_lines)


def main():
    parser = argparse.ArgumentParser(description="Fetch weather and write to vault")
    parser.add_argument("--vault", help="Vault path (default: from config)")
    parser.add_argument("--lat", type=float, default=38.9072, help="Latitude (default: DC)")
    parser.add_argument("--lon", type=float, default=-77.0369, help="Longitude (default: DC)")
    parser.add_argument("--days", type=int, default=3, help="Forecast days (default: 3)")
    args = parser.parse_args()

    logger = setup_logging("weather")
    state = SyncState("weather")

    config = get_config()
    vault_path = args.vault or config.get("vault_path", "~/Documents/Achaean")

    # Use config location if CLI args are at defaults
    location = config.get("location", {})
    lat = args.lat if args.lat != 38.9072 else location.get("latitude", 38.9072)
    lon = args.lon if args.lon != -77.0369 else location.get("longitude", -77.0369)

    try:
        writer = VaultWriter(vault_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    logger.info(f"Fetching {args.days}-day forecast for ({lat}, {lon})")

    try:
        data = fetch_weather(lat, lon, args.days)
    except URLError as e:
        logger.error(f"Failed to fetch weather: {e}")
        sys.exit(1)

    daily = data["daily"]
    files_written = 0

    for i in range(len(daily["time"])):
        frontmatter, body = format_day(daily, i)
        date_str = daily["time"][i]
        filename = f"{date_str}.md"

        path = writer.write_data_file(
            folder="weather",
            filename=filename,
            frontmatter=frontmatter,
            body=body,
            overwrite=True,
        )
        logger.info(f"Wrote {path}")
        files_written += 1

    state.touch_synced()
    logger.info(f"Done. {files_written} weather files written.")


if __name__ == "__main__":
    main()
