import re

with open('paper14-simulator-aware-v13.html', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print(f'Lines: {len(lines)}')
print(f'Bytes: {len(content.encode("utf-8"))}')

for tag in ['h2','h3','h4','table','pre','div','ul','ol','p']:
    opens = len(re.findall(f'<{tag}[ >]', content))
    closes = len(re.findall(f'</{tag}>', content))
    status = 'OK' if opens == closes else f'MISMATCH open={opens} close={closes}'
    print(f'  <{tag}>: {opens}/{closes} — {status}')

tables = re.findall(r'Table (\d+)\.', content)
print(f'Tables: {sorted(set(int(t) for t in tables))}')

refs = sorted(set(int(r) for r in re.findall(r'\[(\d+)\]', content)))
print(f'Refs: {refs}')
