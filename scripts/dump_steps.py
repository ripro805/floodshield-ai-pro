import json

with open(r'C:\Users\rifat\.gemini\antigravity\brain\7d01ef13-74d7-40b7-92e9-7f1769680eab\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        idx = data.get('step_index')
        if idx in [1296, 1297, 1302, 1303, 1304, 1305, 1306, 1307, 1308, 1309]:
            stype = data.get('type')
            print(f"==================== STEP {idx} ({stype}) ====================")
            content = data.get('content', '')
            if isinstance(content, str):
                print(content)
            print("\n")
