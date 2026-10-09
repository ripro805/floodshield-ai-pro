from app.database import SessionLocal
from app.history_models import WeeklyHistory
s = SessionLocal()
rows = s.query(WeeklyHistory).limit(15).all()
for r in rows:
    print(repr(r.district), r.week_ending, r.weekly_cases, r.rainfall_mm, r.flood_depth_cm, r.sanitation_score)
