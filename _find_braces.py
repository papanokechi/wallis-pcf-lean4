import re
lines = open('breakthrough_engine_v7.py', encoding='utf-8').readlines()
in_tpl = False
for i, line in enumerate(lines):
    if 'V7_HTML_TEMPLATE = r' in line:
        in_tpl = True
        continue
    if in_tpl and line.strip() == '"""':
        break
    if in_tpl:
        for m in re.finditer(r'(?<!\{)\{(?!\{)', line):
            pos = m.start()
            ctx = line[max(0,pos-10):pos+20].strip()
            print(f"L{i+1}: col={pos}  ...{ctx}...")
