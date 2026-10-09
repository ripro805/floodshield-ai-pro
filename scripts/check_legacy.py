import sys
sys.path.insert(0, '.')
from app.database import SessionLocal
from app.reference_models import Location, DistrictEnv, SatelliteExtent
s = SessionLocal()
for table_name, table in [("Location", Location), ("DistrictEnv", DistrictEnv), ("SatelliteExtent", SatelliteExtent)]:
    rows = s.query(table).all()
    names = set()
    for r in rows:
        for col in ['district', 'name']:
            if hasattr(r, col):
                v = getattr(r, col)
                if v: names.add(v)
    print(f"{table_name} districts ({len(names)}):")
    for n in sorted(names):
        if n in ('Barisal', 'Bogra', 'Chapainawabganj', 'Comilla', 'Chittagong', 'Jessore'):
            print(f"  {n}  <-- legacy")
        else:
            pass
