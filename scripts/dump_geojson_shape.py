import sys, json
sys.path.insert(0, '.')
from app.database import SessionLocal
from app.reference_models import SatelliteExtent
s = SessionLocal()
for d in ['Feni', 'Chattogram', 'Cumilla', 'Sylhet']:
    r = s.query(SatelliteExtent).filter(SatelliteExtent.district.ilike(d)).first()
    g = r.geojson
    print(f"--- {d} ---")
    print("  top-level type:", g.get('type') if isinstance(g, dict) else type(g).__name__)
    if isinstance(g, dict) and g.get('type') == 'FeatureCollection':
        for f in g.get('features', []):
            geom = f.get('geometry', {})
            print("  feature type:", geom.get('type'))
            coords = geom.get('coordinates')
            if coords and isinstance(coords, list) and len(coords) > 0:
                first = coords[0]
                if isinstance(first, list):
                    print("  first coord outer len:", len(first))
                    if len(first) > 0 and isinstance(first[0], list):
                        print("  first coord inner len:", len(first[0]))
                        print("  first inner sample:", first[0][:3] if isinstance(first[0], list) else first[0])
