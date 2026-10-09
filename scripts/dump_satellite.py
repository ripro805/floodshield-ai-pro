import sys
sys.path.insert(0, ".")
from app.database import SessionLocal
from app.reference_models import SatelliteExtent
s = SessionLocal()
rows = s.query(SatelliteExtent).all()
for r in rows:
    print(repr(r.district), r.event_label)
