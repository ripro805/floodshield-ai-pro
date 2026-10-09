import sys
sys.path.insert(0, '.')
from app.database import SessionLocal
from app.reference_models import Location, SatelliteExtent
s = SessionLocal()
db_d = sorted({r.district for r in s.query(Location).filter(Location.upazila.is_(None)).all()})
sat_d = sorted({r.district for r in s.query(SatelliteExtent).all()})
print(f"DB districts: {len(db_d)}, satellite: {len(sat_d)}")
missing = [d for d in db_d if d not in sat_d]
print(f"Missing from satellite_extents: {missing}")
print(f"Total satellite rows: {s.query(SatelliteExtent).count()}")
# Show a sample
print("Sample satellite rows:")
for r in s.query(SatelliteExtent).limit(3).all():
    print(f"  {r.district}  label={r.event_label!r}  source={r.source!r}")
