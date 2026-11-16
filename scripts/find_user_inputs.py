import json

with open(r'C:\Users\rifat\.gemini\antigravity\brain\7d01ef13-74d7-40b7-92e9-7f1769680eab\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        if data.get('type') == 'USER_INPUT':
            content = data.get('content', '')
            print(f"STEP {data.get('step_index')}: {content[:120]}...")
