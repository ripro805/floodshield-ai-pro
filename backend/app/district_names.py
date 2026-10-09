"""
Canonical English -> Bangla mapping for all 64 Bangladesh districts.

Single source of truth used by:
  - `app.services.agent_tools` (district resolution)
  - `GET /locations/bangla` (frontend display)
  - the admin Data Status page (so the table shows "ফেনী / Feni")

Keys are case-insensitive English canonical names matching the entries
seeded into the `locations` table; values are the official Bangla
spellings as used by the Bangladesh government gazette.

If a district appears in the DB with a casing or spelling that isn't in
this map, the lookup is a no-op (the frontend falls back to displaying
the English name only).
"""
from __future__ import annotations

from typing import Dict, List


EN_TO_BN: Dict[str, str] = {
    "Bagerhat": "বাগেরহাট",
    "Bandarban": "বান্দরবান",
    "Barguna": "বরগুনা",
    "Barishal": "বরিশাল",
    "Bhola": "ভোলা",
    "Bogura": "বগুড়া",
    "Brahmanbaria": "ব্রাহ্মণবাড়িয়া",
    "Chapainawabganj": "চাঁপাইনবাবগঞ্জ",
    "Chandpur": "চাঁদপুর",
    "Chattogram": "চট্টগ্রাম",
    "Chuadanga": "চুয়াডাঙ্গা",
    "Cox's Bazar": "কক্সবাজার",
    "Cumilla": "কুমিল্লা",
    "Dhaka": "ঢাকা",
    "Dinajpur": "দিনাজপুর",
    "Faridpur": "ফরিদপুর",
    "Feni": "ফেনী",
    "Gaibandha": "গাইবান্ধা",
    "Gazipur": "গাজীপুর",
    "Gopalganj": "গোপালগঞ্জ",
    "Habiganj": "হবিগঞ্জ",
    "Jamalpur": "জামালপুর",
    "Jashore": "যশোর",
    "Jhalokati": "ঝালকাঠি",
    "Jhenaidah": "ঝিনাইদহ",
    "Joypurhat": "জয়পুরহাট",
    "Khagrachhari": "খাগড়াছড়ি",
    "Khulna": "খুলনা",
    "Kishoreganj": "কিশোরগঞ্জ",
    "Kurigram": "কুড়িগ্রাম",
    "Kushtia": "কুষ্টিয়া",
    "Lakshmipur": "লক্ষ্মীপুর",
    "Lalmonirhat": "লালমনিরহাট",
    "Madaripur": "মাদারীপুর",
    "Magura": "মাগুরা",
    "Manikganj": "মানিকগঞ্জ",
    "Meherpur": "মেহেরপুর",
    "Moulvibazar": "মৌলভীবাজার",
    "Munshiganj": "মুন্সিগঞ্জ",
    "Mymensingh": "ময়মনসিংহ",
    "Naogaon": "নওগাঁ",
    "Narail": "নড়াইল",
    "Narayanganj": "নারায়ণগঞ্জ",
    "Narsingdi": "নরসিংদী",
    "Natore": "নাটোর",
    "Netrokona": "নেত্রকোনা",
    "Nilphamari": "নীলফামারী",
    "Noakhali": "নোয়াখালী",
    "Pabna": "পাবনা",
    "Panchagarh": "পঞ্চগড়",
    "Patuakhali": "পটুয়াখালী",
    "Pirojpur": "পিরোজপুর",
    "Rajbari": "রাজবাড়ী",
    "Rajshahi": "রাজশাহী",
    "Rangamati": "রাঙ্গামাটি",
    "Rangpur": "রংপুর",
    "Satkhira": "সাতক্ষীরা",
    "Shariatpur": "শরীয়তপুর",
    "Sherpur": "শেরপুর",
    "Sirajganj": "সিরাজগঞ্জ",
    "Sunamganj": "সুনামগঞ্জ",
    "Sylhet": "সিলেট",
    "Tangail": "টাঙ্গাইল",
    "Thakurgaon": "ঠাকুরগাঁও",
}


def get_bn_name(en_name: str) -> str | None:
    """Look up the Bangla name for an English district; case-insensitive.

    Returns None if not found (e.g. for a misspelled district coming
    from the DB).  Callers should fall back to displaying only the
    English name.
    """
    if not en_name:
        return None
    if en_name in EN_TO_BN:
        return EN_TO_BN[en_name]
    # Case-insensitive fallback
    for k, v in EN_TO_BN.items():
        if k.lower() == en_name.lower():
            return v
    return None


def all_pairs() -> List[dict]:
    """Return every canonical pair as {en, bn} -- used by the frontend
    to build a local lookup table without a per-keystroke API call."""
    return [{"en": en, "bn": bn} for en, bn in sorted(EN_TO_BN.items())]
