p = r'D:\KnowledgeVault\Project\FloodShield\frontend\app\dashboard\[district]\page.tsx'
text = open(p, 'rb').read().decode('utf-8')
i = text.index('Breadcrumb')
end = text.index('/* Header */', i)
print(repr(text[i:end]))
print('---')
print('---len---', end - i)