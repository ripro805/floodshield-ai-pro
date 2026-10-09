from app.database import SessionLocal
from app.reference_models import SatelliteExtent
s = SessionLocal()
for d in ['Feni','Chattogram','Cumilla','Sylhet','Dhaka']:
    r = s.query(SatelliteExtent).filter(SatelliteExtent.district.ilike(d)).first()
    print(d, '->', 'OK' if r else 'NONE', '-', getattr(r,'event_label',None) if r else None)
