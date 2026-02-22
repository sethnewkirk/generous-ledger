"""Tests for weather.py — weather formatting and condition classification."""

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from weather import simplify_condition, WMO_CODES, format_day


class TestSimplifyCondition(unittest.TestCase):
    def test_clear_codes(self):
        self.assertEqual(simplify_condition(0), "clear")
        self.assertEqual(simplify_condition(1), "clear")

    def test_cloudy_codes(self):
        self.assertEqual(simplify_condition(2), "partly-cloudy")
        self.assertEqual(simplify_condition(3), "overcast")

    def test_fog_codes(self):
        self.assertEqual(simplify_condition(45), "fog")
        self.assertEqual(simplify_condition(48), "fog")

    def test_rain_codes(self):
        self.assertEqual(simplify_condition(61), "rain")
        self.assertEqual(simplify_condition(63), "rain")
        self.assertEqual(simplify_condition(65), "rain")

    def test_snow_codes(self):
        self.assertEqual(simplify_condition(71), "snow")
        self.assertEqual(simplify_condition(73), "snow")
        self.assertEqual(simplify_condition(75), "snow")

    def test_thunderstorm_codes(self):
        self.assertEqual(simplify_condition(95), "thunderstorm")
        self.assertEqual(simplify_condition(99), "thunderstorm")

    def test_drizzle_codes(self):
        self.assertEqual(simplify_condition(51), "drizzle")
        self.assertEqual(simplify_condition(55), "drizzle")

    def test_shower_codes(self):
        self.assertEqual(simplify_condition(80), "rain-showers")
        self.assertEqual(simplify_condition(85), "snow-showers")


class TestWMOCodes(unittest.TestCase):
    def test_all_codes_have_descriptions(self):
        """All codes used in simplify_condition should have descriptions."""
        for code in [0, 1, 2, 3, 45, 48, 51, 53, 55, 61, 63, 65, 71, 73, 75, 80, 81, 82, 85, 86, 95, 99]:
            self.assertIn(code, WMO_CODES, f"WMO code {code} missing description")


class TestFormatDay(unittest.TestCase):
    def make_daily(self, **overrides):
        """Create a minimal daily data structure for testing."""
        defaults = {
            "time": ["2026-02-21"],
            "weather_code": [2],
            "temperature_2m_max": [55.4],
            "temperature_2m_min": [38.2],
            "precipitation_probability_max": [10],
            "sunrise": ["2026-02-21T06:45"],
            "sunset": ["2026-02-21T17:55"],
            "wind_speed_10m_max": [12.3],
        }
        defaults.update(overrides)
        return defaults

    def test_basic_format(self):
        daily = self.make_daily()
        fm, body = format_day(daily, 0)

        self.assertEqual(fm["type"], "weather-daily")
        self.assertEqual(fm["date"], "2026-02-21")
        self.assertEqual(fm["high_f"], 55)
        self.assertEqual(fm["low_f"], 38)
        self.assertEqual(fm["condition"], "partly-cloudy")
        self.assertEqual(fm["precipitation_chance"], 10)
        self.assertEqual(fm["source"], "open-meteo")
        self.assertIn("data", fm["tags"])
        self.assertIn("weather", fm["tags"])

    def test_body_contains_description(self):
        daily = self.make_daily()
        _, body = format_day(daily, 0)

        self.assertIn("Partly Cloudy", body)
        self.assertIn("55°F", body)
        self.assertIn("38°F", body)

    def test_high_wind_note(self):
        daily = self.make_daily(wind_speed_10m_max=[25.0])
        _, body = format_day(daily, 0)
        self.assertIn("Windy", body)
        self.assertIn("25 mph", body)

    def test_no_wind_note_for_calm(self):
        daily = self.make_daily(wind_speed_10m_max=[8.0])
        _, body = format_day(daily, 0)
        self.assertNotIn("Windy", body)

    def test_precipitation_note(self):
        daily = self.make_daily(precipitation_probability_max=[75])
        _, body = format_day(daily, 0)
        self.assertIn("75%", body)

    def test_no_precipitation_note_for_zero(self):
        daily = self.make_daily(precipitation_probability_max=[0])
        _, body = format_day(daily, 0)
        self.assertNotIn("Precipitation", body)

    def test_sunrise_sunset(self):
        daily = self.make_daily()
        fm, body = format_day(daily, 0)
        self.assertEqual(fm["sunrise"], "06:45")
        self.assertEqual(fm["sunset"], "17:55")
        self.assertIn("06:45", body)
        self.assertIn("17:55", body)

    def test_snow_condition(self):
        daily = self.make_daily(weather_code=[75])
        fm, _ = format_day(daily, 0)
        self.assertEqual(fm["condition"], "snow")
        self.assertEqual(fm["wmo_code"], 75)


class TestFormatDayFinance(unittest.TestCase):
    """Test finance adapter formatting."""

    def test_weekly_summary_format(self):
        sys.path.append(str(Path(__file__).parent.parent))
        from finance import format_weekly_summary
        from datetime import date

        categories = [
            {"group": "Bills", "name": "Rent", "budgeted": 1500, "activity": 1500, "balance": 0},
            {"group": "Food", "name": "Groceries", "budgeted": 400, "activity": 450, "balance": -50},
            {"group": "Food", "name": "Dining Out", "budgeted": 100, "activity": 50, "balance": 50},
        ]

        week_start = date(2026, 2, 16)
        fm, body = format_weekly_summary(categories, week_start)

        self.assertEqual(fm["type"], "finance-weekly")
        self.assertEqual(fm["total_budgeted"], 2000)
        self.assertEqual(fm["total_spent"], 2000)
        self.assertIn("Groceries", fm["over_budget_categories"])
        self.assertIn("OVER", body)
        self.assertIn("Groceries", body)


if __name__ == "__main__":
    unittest.main()
