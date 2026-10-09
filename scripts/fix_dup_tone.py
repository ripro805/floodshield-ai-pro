p = r"D:\KnowledgeVault\Project\FloodShield\frontend\app\dashboard\[district]\page.tsx"
t = open(p, encoding="utf-8").read()
needle = "          tone={issueRollup.data && (issueRollup.data.open + issueRollup.data.ack) > 0 ? '#F59E0B' : '#34D399'}\n          tone={issueRollup.data && (issueRollup.data.open + issueRollup.data.ack) > 0 ? '#F59E0B' : '#34D399'}\n          index={5}\n"
if needle in t:
    t = t.replace(needle, "          tone={issueRollup.data && (issueRollup.data.open + issueRollup.data.ack) > 0 ? '#F59E0B' : '#34D399'}\n          index={5}\n", 1)
    open(p, "w", encoding="utf-8").write(t)
    print("OK")
else:
    print("no match")
