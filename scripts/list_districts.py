import re
text = open("D:/KnowledgeVault/Project/FloodShield/frontend/lib/types.ts", encoding="utf-8").read()
m = re.search(r"BANGLADESH_DISTRICTS = \[(.+?)\];", text, re.DOTALL)
if m:
    arr = m.group(1)
    items = re.findall(r"'([^']+)'", arr)
    print(f"Frontend BANGLADESH_DISTRICTS count: {len(items)}")
    for i in items:
        print(f"  {i}")
