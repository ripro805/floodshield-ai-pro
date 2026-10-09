import re, sys
sys.path.insert(0, ".")
text = open("D:/KnowledgeVault/Project/FloodShield/frontend/lib/types.ts", encoding="utf-8").read()
m = re.search(r"BANGLADESH_DISTRICTS = \[(.+?)\];", text, re.DOTALL)
arr = m.group(1)
# Use a smarter tokenizer that handles escaped apostrophes
items = re.findall(r"'((?:\\'|[^'])*)'", arr)
print(f"Frontend count: {len(items)}")
# Compare with DB
from app.database import SessionLocal
from app.reference_models import Location
s = SessionLocal()
db = sorted({r.district for r in s.query(Location).filter(Location.upazila.is_(None)).all()})
fe = set(items)
print(f"DB count: {len(db)}")
print("In DB but not in frontend:", [d for d in db if d not in fe])
print("In frontend but not in DB:", [d for d in fe if d not in db])
