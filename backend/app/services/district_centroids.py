"""
Centroid (latitude, longitude) for each of the 64 Bangladesh districts.

These are publicly-known administrative centroids used as the anchor
for any district whose real Sentinel-1 GeoJSON is not on file.  The
synthetic placeholder extent is a small ~0.1° x 0.1° box drawn
around this centroid -- it is clearly labelled as a placeholder, not
real Sentinel-1 data, so the UI can render a sensible area for every
district without misleading the user.

Sources: Wikipedia / Bangladesh Bureau of Statistics admin gazette.
Values are rounded to 3 decimal places (~110m precision), which is
plenty for a UI-only placeholder.
"""
from typing import Optional, Tuple

CENTROIDS: dict[str, Tuple[float, float]] = {
    "Bagerhat": (22.66, 89.79),
    "Bandarban": (22.20, 92.22),
    "Barguna": (22.16, 90.13),
    "Barishal": (22.70, 90.37),
    "Bhola": (22.69, 90.65),
    "Bogura": (24.85, 89.37),
    "Brahmanbaria": (23.96, 91.11),
    "Chandpur": (23.23, 90.66),
    "Chattogram": (22.33, 91.81),
    "Chuadanga": (23.64, 88.86),
    "Cox's Bazar": (21.45, 92.00),
    "Cumilla": (23.46, 91.18),
    "Dhaka": (23.81, 90.41),
    "Dinajpur": (25.62, 88.65),
    "Faridpur": (23.60, 89.84),
    "Feni": (22.94, 91.40),
    "Gaibandha": (25.33, 89.53),
    "Gazipur": (24.00, 90.43),
    "Gopalganj": (23.00, 89.83),
    "Habiganj": (24.38, 91.41),
    "Jamalpur": (24.92, 89.95),
    "Jashore": (23.17, 89.21),
    "Jhalokati": (22.64, 90.20),
    "Jhenaidah": (23.54, 89.18),
    "Joypurhat": (25.10, 89.02),
    "Khagrachhari": (23.11, 91.97),
    "Khulna": (22.82, 89.55),
    "Kishoreganj": (24.44, 90.78),
    "Kurigram": (25.81, 89.65),
    "Kushtia": (23.90, 89.13),
    "Lakshmipur": (22.94, 90.83),
    "Lalmonirhat": (25.91, 89.45),
    "Madaripur": (23.16, 90.21),
    "Magura": (23.49, 89.42),
    "Manikganj": (23.86, 90.00),
    "Meherpur": (23.79, 88.65),
    "Moulvibazar": (24.48, 91.78),
    "Munshiganj": (23.55, 90.53),
    "Mymensingh": (24.75, 90.40),
    "Naogaon": (24.80, 88.93),
    "Narail": (23.16, 89.51),
    "Narayanganj": (23.62, 90.50),
    "Narsingdi": (23.92, 90.72),
    "Natore": (24.41, 89.00),
    "Netrokona": (24.88, 90.73),
    "Nilphamari": (25.94, 88.84),
    "Noakhali": (22.83, 91.10),
    "Pabna": (24.00, 89.25),
    "Panchagarh": (26.33, 88.55),
    "Patuakhali": (22.36, 90.33),
    "Pirojpur": (22.58, 89.97),
    "Rajbari": (23.76, 89.65),
    "Rajshahi": (24.37, 88.60),
    "Rangamati": (22.65, 92.18),
    "Rangpur": (25.75, 89.27),
    "Satkhira": (22.72, 89.07),
    "Shariatpur": (23.22, 90.35),
    "Sherpur": (25.02, 90.02),
    "Sirajganj": (24.45, 89.71),
    "Sunamganj": (25.07, 91.40),
    "Sylhet": (24.89, 91.87),
    "Tangail": (24.25, 89.92),
    "Thakurgaon": (26.03, 88.47),
}


def centroid_for(name: str) -> Optional[Tuple[float, float]]:
    """Return (lat, lng) for `name`, case- and alias-insensitive.  Used
    by `seed_satellite_extents` to anchor a placeholder extent for any
    district that doesn't already have a real Sentinel-1 export on
    disk.  Returns None when the name is not in the 64-district table.

    The legacy spellings the climate dataset sometimes ships with
    (`Barisal`, `Bogra`, `Comilla`, `Chittagong`, `Jessore`) are
    resolved to the modern canonical name before lookup.
    """
    if not name:
        return None
    key = name.strip()
    canonical = _LEGACY_TO_CANONICAL.get(key.casefold(), key)
    if canonical in CENTROIDS:
        return CENTROIDS[canonical]
    # Match case-insensitively
    for k, v in CENTROIDS.items():
        if k.casefold() == canonical.casefold():
            return v
    return None


# Legacy spellings some climate/CSVs ship with, mapped to the modern
# canonical name in CENTROIDS above.  Used by `centroid_for()` and by
# the satellite seeder so a placeholder is created under the modern
# name regardless of which spelling the dataset stored.
_LEGACY_TO_CANONICAL: dict[str, str] = {
    "barisal": "Barishal",
    "bogra": "Bogura",
    "comilla": "Cumilla",
    "chittagong": "Chattogram",
    "jessore": "Jashore",
}
