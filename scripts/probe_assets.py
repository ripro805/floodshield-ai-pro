"""Check whether the bundled JS for /dashboard/[district] actually
contains the AssessmentMap code and the geojson rendering paths."""
import re, glob
files = glob.glob("D:/KnowledgeVault/Project/FloodShield/frontend/.next/static/chunks/**/*.js", recursive=True)
matches = []
for f in files:
    try:
        text = open(f, encoding="utf-8", errors="ignore").read()
    except Exception:
        continue
    for kw in ['AssessmentMap', 'flood_pixel_ratio', 'makeSegmentationSVG', '38BDF8', 'L.geoJSON', 'svgOverlay', 'GeoJSON', 'L.rectangle', 'FALLBACK_CENTERS']:
        if kw in text:
            matches.append((f, kw))
for m in matches[:40]:
    print(m)
