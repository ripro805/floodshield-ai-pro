import sys
p = r"D:\KnowledgeVault\Project\FloodShield\frontend\lib\api.ts"
text = open(p, "r", encoding="utf-8").read()
needle = "  return data;\n  return data;\n}\n"
if needle in text:
    text = text.replace(needle, "  return data;\n}\n", 1)
    open(p, "w", encoding="utf-8").write(text)
    print("OK: fixed duplicate")
else:
    print("no match")
