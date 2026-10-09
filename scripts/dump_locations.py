import sys
sys.path.insert(0, '.')
from app.database import SessionLocal
from app.reference_models import Location
s = SessionLocal()
rows = s.query(Location).filter(Location.upazila == None).all()
print(f"Total district rows: {len(rows)}")
print("Cols:", [c for c in rows[0].__table__.columns.keys()])
for r in rows[:5]:
    print(" district=", r.district, "upazila=", r.upazila, "kind=", r.kind)
