import json

with open(r'C:\Users\rifat\.gemini\antigravity\brain\7d01ef13-74d7-40b7-92e9-7f1769680eab\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        idx = data.get('step_index')
        stype = data.get('type')
        if idx in [4, 5, 6, 7, 8, 9, 10]:
            print(f'*** STEP {idx} - TYPE: {stype} ***')
            content = data.get('content', '')
            if isinstance(content, str):
                print(content[:1500])
                print('\n---\n')
