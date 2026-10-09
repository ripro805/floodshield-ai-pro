import sys
sys.path.insert(0, '.')
from app.database import SessionLocal
from sqlalchemy import text
s = SessionLocal()
print("satellite_extents:", s.execute(text("select count(*) from satellite_extents")).scalar())
print("weekly_history:", s.execute(text("select count(*) from weekly_history")).scalar())
print("locations:", s.execute(text("select count(*) from locations")).scalar())
print("district_env:", s.execute(text("select count(*) from district_env")).scalar())
print("hospitals:", s.execute(text("select count(*) from hospitals")).scalar())
print("district_hospital_aggregates:", s.execute(text("select count(*) from district_hospital_aggregates")).scalar())
