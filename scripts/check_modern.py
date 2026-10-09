import sys
sys.path.insert(0, '.')
from app.database import SessionLocal
from app.reference_models import SatelliteExtent
s = SessionLocal()
moderns = ['Barishal', 'Bogura', 'Cumilla', 'Nawabganj', 'Chattogram']
for m in moderns:
    r = s.query(SatelliteExtent).filter(SatelliteExtent.district.ilike(m)).first()
    print(f"  {m}: {'OK' if r else 'MISSING'}  {r.event_label if r else ''}")
