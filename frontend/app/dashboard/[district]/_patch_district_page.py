"""Pass district to RiskSummaryCard and replace the <h1>{district}</h1> with DistrictName."""
from pathlib import Path
p = Path(r"D:\KnowledgeVault\Project\FloodShield\frontend\app\dashboard\[district]\page.tsx")
t = p.read_text(encoding="utf-8")

# 1) Add DistrictName import after GlassCard import
old1 = "import GlassCard from '@/components/cards/GlassCard';\n"
new1 = "import GlassCard from '@/components/cards/GlassCard';\nimport DistrictName from '@/components/common/DistrictName';\n"
if t.count(old1) != 1:
    raise SystemExit(f"GlassCard import anchor count {t.count(old1)}")
t = t.replace(old1, new1)

# 2) Replace the <h1>{district}</h1> with DistrictName
old2 = '''          <div>
            <h1 className="text-4xl font-black text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
              {district}
            </h1>
            <p className="text-white/40 mt-1">District risk assessment · Bangladesh</p>
          </div>'''
new2 = '''          <div>
            <DistrictName en={district} size="lg" />
            <p className="text-white/40 mt-2">District risk assessment · Bangladesh</p>
          </div>'''
if t.count(old2) != 1:
    raise SystemExit(f"h1 anchor count {t.count(old2)}")
t = t.replace(old2, new2)

# 3) Pass district to RiskSummaryCard
old3 = '<RiskSummaryCard data={flood} />'
new3 = '<RiskSummaryCard data={flood} district={district} />'
if t.count(old3) != 1:
    raise SystemExit(f"RiskSummaryCard anchor count {t.count(old3)}")
t = t.replace(old3, new3)

# 4) Replace the breadcrumb <span className="text-white font-semibold">{district}</span>
#    with DistrictName (small, no background).
old4 = '''        <span className="text-white font-semibold">{district}</span>'''
new4 = '''        <DistrictName en={district} size="sm" layout="inline" />'''
if t.count(old4) != 1:
    raise SystemExit(f"breadcrumb anchor count {t.count(old4)}")
t = t.replace(old4, new4)

p.write_text(t, encoding="utf-8")
print("OK")
