"""Distance and ETA calculations with geocoding cache.

R1 uses a simple lookup table for known Florida locations.
Production will integrate Google Maps or HERE geocoding API with DynamoDB cache.
"""

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

# Precomputed distances (miles) from common origins to Juno Beach, FL (FPL HQ)
# Used as a lightweight geocoding substitute for R1 development
# Covers: Florida, Georgia, Alabama, Mississippi, Louisiana, Tennessee,
#         South Carolina, North Carolina, Virginia, Texas, and other SE states
_DISTANCE_CACHE: dict[str, float] = {
    # ── Florida ──────────────────────────────────────────────────
    "juno beach, fl": 0.0,
    "west palm beach, fl": 15.0,
    "palm beach gardens, fl": 8.0,
    "jupiter, fl": 5.0,
    "boca raton, fl": 30.0,
    "delray beach, fl": 25.0,
    "boynton beach, fl": 20.0,
    "fort lauderdale, fl": 55.0,
    "hollywood, fl": 65.0,
    "miami, fl": 85.0,
    "miami beach, fl": 90.0,
    "homestead, fl": 110.0,
    "key west, fl": 270.0,
    "key largo, fl": 140.0,
    "pompano beach, fl": 45.0,
    "deerfield beach, fl": 40.0,
    "coral springs, fl": 50.0,
    "plantation, fl": 60.0,
    "davie, fl": 60.0,
    "pembroke pines, fl": 70.0,
    "hialeah, fl": 80.0,
    "fort pierce, fl": 60.0,
    "port st. lucie, fl": 55.0,
    "stuart, fl": 35.0,
    "vero beach, fl": 85.0,
    "melbourne, fl": 120.0,
    "cocoa, fl": 140.0,
    "titusville, fl": 155.0,
    "cape canaveral, fl": 145.0,
    "daytona beach, fl": 200.0,
    "new smyrna beach, fl": 190.0,
    "deland, fl": 195.0,
    "sanford, fl": 175.0,
    "orlando, fl": 160.0,
    "kissimmee, fl": 170.0,
    "winter park, fl": 165.0,
    "altamonte springs, fl": 170.0,
    "clermont, fl": 185.0,
    "ocala, fl": 240.0,
    "the villages, fl": 220.0,
    "leesburg, fl": 210.0,
    "lakeland, fl": 185.0,
    "winter haven, fl": 175.0,
    "bartow, fl": 180.0,
    "sebring, fl": 140.0,
    "okeechobee, fl": 100.0,
    "clewiston, fl": 100.0,
    "belle glade, fl": 60.0,
    "tampa, fl": 200.0,
    "st. petersburg, fl": 215.0,
    "clearwater, fl": 220.0,
    "brandon, fl": 195.0,
    "plant city, fl": 190.0,
    "bradenton, fl": 195.0,
    "sarasota, fl": 185.0,
    "venice, fl": 175.0,
    "port charlotte, fl": 155.0,
    "punta gorda, fl": 150.0,
    "fort myers, fl": 150.0,
    "cape coral, fl": 155.0,
    "naples, fl": 160.0,
    "marco island, fl": 170.0,
    "gainesville, fl": 290.0,
    "palatka, fl": 260.0,
    "st. augustine, fl": 280.0,
    "jacksonville, fl": 340.0,
    "jacksonville beach, fl": 345.0,
    "fernandina beach, fl": 360.0,
    "lake city, fl": 340.0,
    "live oak, fl": 370.0,
    "tallahassee, fl": 470.0,
    "panama city, fl": 560.0,
    "panama city beach, fl": 565.0,
    "destin, fl": 600.0,
    "fort walton beach, fl": 610.0,
    "crestview, fl": 620.0,
    "pensacola, fl": 640.0,
    "perry, fl": 410.0,
    "cross city, fl": 350.0,
    "crystal river, fl": 260.0,
    "spring hill, fl": 235.0,
    "brooksville, fl": 230.0,
    "inverness, fl": 250.0,
    # ── Georgia ──────────────────────────────────────────────────
    "atlanta, ga": 550.0,
    "marietta, ga": 570.0,
    "roswell, ga": 565.0,
    "alpharetta, ga": 575.0,
    "kennesaw, ga": 575.0,
    "smyrna, ga": 560.0,
    "decatur, ga": 545.0,
    "lawrenceville, ga": 555.0,
    "duluth, ga": 560.0,
    "norcross, ga": 555.0,
    "peachtree city, ga": 530.0,
    "newnan, ga": 520.0,
    "carrollton, ga": 540.0,
    "rome, ga": 620.0,
    "dalton, ga": 650.0,
    "gainesville, ga": 580.0,
    "athens, ga": 560.0,
    "macon, ga": 490.0,
    "warner robins, ga": 480.0,
    "milledgeville, ga": 500.0,
    "augusta, ga": 530.0,
    "columbus, ga": 540.0,
    "albany, ga": 430.0,
    "valdosta, ga": 380.0,
    "tifton, ga": 420.0,
    "waycross, ga": 370.0,
    "brunswick, ga": 370.0,
    "savannah, ga": 420.0,
    "statesboro, ga": 430.0,
    "hinesville, ga": 400.0,
    "vidalia, ga": 410.0,
    "dublin, ga": 450.0,
    "cordele, ga": 440.0,
    "americus, ga": 460.0,
    "thomasville, ga": 410.0,
    "moultrie, ga": 400.0,
    "douglas, ga": 390.0,
    # ── Alabama ──────────────────────────────────────────────────
    "birmingham, al": 700.0,
    "huntsville, al": 780.0,
    "montgomery, al": 620.0,
    "mobile, al": 730.0,
    "tuscaloosa, al": 720.0,
    "auburn, al": 590.0,
    "opelika, al": 590.0,
    "dothan, al": 530.0,
    "enterprise, al": 540.0,
    "troy, al": 570.0,
    "selma, al": 660.0,
    "gadsden, al": 730.0,
    "anniston, al": 700.0,
    "florence, al": 820.0,
    "decatur, al": 790.0,
    "phenix city, al": 540.0,
    "prattville, al": 630.0,
    "daphne, al": 720.0,
    "fairhope, al": 720.0,
    "gulf shores, al": 740.0,
    # ── Mississippi ───────────────────────────────────────────────
    "jackson, ms": 780.0,
    "gulfport, ms": 750.0,
    "biloxi, ms": 750.0,
    "hattiesburg, ms": 720.0,
    "meridian, ms": 720.0,
    "tupelo, ms": 870.0,
    "oxford, ms": 880.0,
    "columbus, ms": 770.0,
    "starkville, ms": 780.0,
    "vicksburg, ms": 820.0,
    "natchez, ms": 830.0,
    "laurel, ms": 720.0,
    "pascagoula, ms": 740.0,
    "ocean springs, ms": 750.0,
    # ── Louisiana ────────────────────────────────────────────────
    "new orleans, la": 850.0,
    "baton rouge, la": 830.0,
    "shreveport, la": 1000.0,
    "lafayette, la": 870.0,
    "lake charles, la": 920.0,
    "monroe, la": 930.0,
    "alexandria, la": 880.0,
    "houma, la": 870.0,
    "slidell, la": 830.0,
    "kenner, la": 850.0,
    "metairie, la": 850.0,
    # ── Tennessee ────────────────────────────────────────────────
    "nashville, tn": 870.0,
    "memphis, tn": 950.0,
    "knoxville, tn": 780.0,
    "chattanooga, tn": 700.0,
    "clarksville, tn": 900.0,
    "murfreesboro, tn": 860.0,
    "franklin, tn": 870.0,
    "johnson city, tn": 830.0,
    "jackson, tn": 920.0,
    "cookeville, tn": 820.0,
    "columbia, tn": 870.0,
    # ── South Carolina ───────────────────────────────────────────
    "columbia, sc": 580.0,
    "charleston, sc": 520.0,
    "greenville, sc": 650.0,
    "spartanburg, sc": 660.0,
    "myrtle beach, sc": 600.0,
    "rock hill, sc": 660.0,
    "florence, sc": 570.0,
    "sumter, sc": 560.0,
    "anderson, sc": 640.0,
    "hilton head, sc": 460.0,
    "beaufort, sc": 470.0,
    "aiken, sc": 560.0,
    "orangeburg, sc": 540.0,
    "north charleston, sc": 520.0,
    # ── North Carolina ───────────────────────────────────────────
    "charlotte, nc": 680.0,
    "raleigh, nc": 750.0,
    "durham, nc": 760.0,
    "greensboro, nc": 740.0,
    "winston-salem, nc": 740.0,
    "fayetteville, nc": 700.0,
    "wilmington, nc": 660.0,
    "asheville, nc": 720.0,
    "high point, nc": 740.0,
    "gastonia, nc": 690.0,
    "concord, nc": 690.0,
    "jacksonville, nc": 720.0,
    "greenville, nc": 760.0,
    "rocky mount, nc": 780.0,
    "hickory, nc": 720.0,
    # ── Virginia ─────────────────────────────────────────────────
    "richmond, va": 850.0,
    "virginia beach, va": 880.0,
    "norfolk, va": 880.0,
    "chesapeake, va": 870.0,
    "newport news, va": 870.0,
    "hampton, va": 870.0,
    "alexandria, va": 920.0,
    "roanoke, va": 830.0,
    "lynchburg, va": 840.0,
    "charlottesville, va": 870.0,
    "fredericksburg, va": 900.0,
    "danville, va": 780.0,
    # ── Texas (major cities) ─────────────────────────────────────
    "houston, tx": 1100.0,
    "dallas, tx": 1200.0,
    "san antonio, tx": 1250.0,
    "austin, tx": 1230.0,
    "fort worth, tx": 1210.0,
    "el paso, tx": 1800.0,
    "corpus christi, tx": 1300.0,
    "beaumont, tx": 1020.0,
    "port arthur, tx": 1030.0,
    "lufkin, tx": 1080.0,
    # ── Other SE / nearby states ─────────────────────────────────
    "st. louis, mo": 1050.0,
    "little rock, ar": 980.0,
    "louisville, ky": 900.0,
    "lexington, ky": 870.0,
    "bowling green, ky": 860.0,
    "washington, dc": 940.0,
    "baltimore, md": 960.0,
}


class GeoCalculationService:
    """Distance and ETA calculations using standard travel pace."""

    def __init__(self, pace_mph: float = 31.25, cache: dict[str, float] | None = None):
        self._pace_mph = pace_mph
        self._cache = cache or _DISTANCE_CACHE
        self._tz = ZoneInfo("America/New_York")

    def calculate_distance_miles(self, origin: str, destination: str) -> float:
        """Return driving distance in miles between two locations.

        R1: uses precomputed lookup table with fuzzy matching.
        Production: geocoding API + DynamoDB cache.
        """
        origin_dist = self._resolve_location(origin)
        dest_dist = self._resolve_location(destination)

        if origin_dist is not None and dest_dist is not None:
            return abs(origin_dist - dest_dist)
        if origin_dist is not None:
            return origin_dist

        # Fallback: return a sentinel that triggers clarification
        return -1.0

    def _resolve_location(self, location: str) -> float | None:
        """Resolve a location string to a distance value from the cache.

        Tries exact match first, then checks if any cache key appears
        within the location string (e.g., 'Downtown Atlanta, GA' matches 'atlanta, ga').
        """
        loc = location.strip().lower()

        # Exact match
        if loc in self._cache:
            return self._cache[loc]

        # Fuzzy: check if any cache key is contained in the location
        for key, dist in self._cache.items():
            # Check if the city name from the cache key appears in the input
            city = key.split(",")[0].strip()
            if city in loc:
                return dist

        # Fuzzy: check if the location contains a known state abbreviation + city
        for key, dist in self._cache.items():
            parts = key.split(",")
            if len(parts) == 2:
                city = parts[0].strip()
                state = parts[1].strip()
                if city in loc or (state in loc and any(word in loc for word in city.split())):
                    return dist

        return None

    def calculate_eta(
        self, origin: str, destination: str, departure_time: str, pace_mph: float | None = None
    ) -> dict[str, Any]:
        """Calculate expected arrival time based on distance and pace."""
        pace = pace_mph or self._pace_mph
        distance = self.calculate_distance_miles(origin, destination)
        if distance < 0:
            return {"error": "Unable to calculate distance — unknown location", "distance_miles": -1}

        hours = distance / pace
        dep = self._parse_time(departure_time)
        arrival = dep + timedelta(hours=hours)

        return {
            "distance_miles": round(distance, 1),
            "expected_duration_hours": round(hours, 2),
            "expected_arrival_time": arrival.isoformat(),
            "expected_arrival_display": arrival.strftime("%-I:%M %p ET"),
        }

    def _parse_time(self, time_str: str) -> datetime:
        """Parse flexible time formats into a datetime. Assumes today + Eastern timezone."""
        import re
        if time_str == "now":
            return datetime.now(self._tz)

        # Try ISO format first
        try:
            return datetime.fromisoformat(time_str)
        except (ValueError, TypeError):
            pass

        today = datetime.now(self._tz).date()
        s = time_str.strip().lower()

        # Military time: "1300", "0400"
        m = re.match(r'^(\d{4})$', s)
        if m:
            h, mn = int(s[:2]), int(s[2:])
            return datetime(today.year, today.month, today.day, h, mn, tzinfo=self._tz)

        # HH:MM format: "04:00", "13:00"
        m = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$', s)
        if m:
            h, mn = int(m.group(1)), int(m.group(2))
            return datetime(today.year, today.month, today.day, h, mn, tzinfo=self._tz)

        # AM/PM: "4 AM", "4:00 PM", "4AM", "4:30pm"
        m = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$', s)
        if m:
            h = int(m.group(1))
            mn = int(m.group(2) or 0)
            if m.group(3) == 'pm' and h != 12:
                h += 12
            if m.group(3) == 'am' and h == 12:
                h = 0
            return datetime(today.year, today.month, today.day, h, mn, tzinfo=self._tz)

        # Fallback: try to parse as-is
        return datetime.now(self._tz)

    def check_plausibility(
        self,
        origin: str,
        destination: str,
        departure_time: str,
        provided_eta: str,
        pace_mph: float | None = None,
        threshold_percent: float = 10.0,
    ) -> dict[str, Any]:
        """Check if provided ETA is plausible against calculated ETA.

        Returns is_plausible, variance_percent, expected_arrival_time.
        """
        calc = self.calculate_eta(origin, destination, departure_time, pace_mph)
        if "error" in calc:
            # Unknown location — skip validation, accept ETA as-is
            return {
                "is_plausible": "unconfirmed",
                "validation_skipped": True,
                "validation_skipped_reason": f"Unable to resolve departure location: {origin}",
                "variance_percent": 0.0,
                "provided_arrival_time": provided_eta,
            }

        expected = datetime.fromisoformat(calc["expected_arrival_time"])
        provided = self._parse_time(provided_eta)
        expected_hours = calc["expected_duration_hours"]

        if expected_hours == 0:
            return {**calc, "provided_arrival_time": provided_eta, "is_plausible": True, "variance_percent": 0.0}

        diff_hours = (provided - expected).total_seconds() / 3600
        variance_pct = abs(diff_hours / expected_hours) * 100

        # Asymmetric plausibility: too fast = implausible, too slow = flagged but accepted
        is_too_fast = diff_hours < 0 and variance_pct > threshold_percent
        is_slow = diff_hours > 0 and variance_pct > threshold_percent

        return {
            "distance_miles": calc["distance_miles"],
            "expected_duration_hours": expected_hours,
            "expected_arrival_time": calc["expected_arrival_time"],
            "expected_arrival_display": calc.get("expected_arrival_display", ""),
            "provided_arrival_time": provided_eta,
            "provided_arrival_display": provided.strftime("%-I:%M %p ET"),
            "variance_percent": round(variance_pct, 1),
            "is_plausible": not is_too_fast,
            "is_slow": is_slow,
            "note": "ETA is slower than expected — flagged for review" if is_slow else "",
        }
