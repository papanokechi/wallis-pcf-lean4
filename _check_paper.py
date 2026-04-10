import re
with open('paper14-ratio-universality-v2.html', 'r', encoding='utf-8') as f:
    html = f.read()
print(f'Total lines: {len(html.splitlines())}')
opens = len(re.findall(r'<div', html))
closes = len(re.findall(r'</div', html))
print(f'<div> opens: {opens}, closes: {closes}')
opens_t = len(re.findall(r'<table', html))
closes_t = len(re.findall(r'</table', html))
print(f'<table> opens: {opens_t}, closes: {closes_t}')
secs = re.findall(r'id="sec(\d+)"', html)
print(f'Sections found: {secs}')
tboxes = len(re.findall(r'theorem-box', html))
cboxes = len(re.findall(r'conjecture-box', html))
nboxes = len(re.findall(r'note-box', html))
wboxes = len(re.findall(r'warning-box', html))
print(f'Boxes: theorem={tboxes}, conjecture={cboxes}, note={nboxes}, warning={wboxes}')
conj_a = [(html[:m.start()].count('\n')+1) for m in re.finditer(r'Conjecture A', html)]
print(f'Remaining "Conjecture A" refs: {len(conj_a)} at lines {conj_a}')
