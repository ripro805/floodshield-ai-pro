p = r"d:\KnowledgeVault\Project\FloodShield\frontend\app\dashboard\resources\directory\HospitalDirectoryView.tsx"
src = open(p, "r", encoding="utf-8").read()
old = "import HospitalEditModal from '@/components/hospital/HospitalEditModal';\nimport HospitalIssueModal from '@/components/hospital/HospitalIssueModal';\n"
new = (
    "import HospitalEditModal from '@/components/hospital/HospitalEditModal';\n"
    "import HospitalIssueModal from '@/components/hospital/HospitalIssueModal';\n"
    "import HospitalDetailModal from '@/components/hospital/HospitalDetailModal';\n"
)
print("match:", src.count(old))
src = src.replace(old, new, 1)
open(p, "w", encoding="utf-8").write(src)
print("done")
