import sys
sys.path.insert(0, '.')
from app.database import SessionLocal
from app.reference_models import Location
from app.services.district_centroids import CENTROIDS
s = SessionLocal()
rows = s.query(Location).filter(Location.upazila.is_(None)).all()
db_districts = sorted({r.district for r in rows})
known = set(CENTROIDS.keys())
missing = [d for d in db_districts if d not in known and d.casefold() not in {k.casefold() for k in known}]
print(f"DB has {len(db_districts)} districts")
print(f"Centroids table has {len(known)} districts")
print(f"Missing from centroids: {missing}")
print(f"DB sample: {db_districts[:5]}")
