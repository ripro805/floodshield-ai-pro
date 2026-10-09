import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import SessionLocal
from app.history_models import WeeklyHistory
s = SessionLocal()
rows = s.query(WeeklyHistory).filter(WeeklyHistory.district.ilike('%feni%')).all()
for r in rows:
    print(repr(r.district), r.week_ending, r.weekly_cases, r.rainfall_mm, r.flood_depth_cm, r.sanitation_score)
