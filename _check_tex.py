import re
from collections import Counter

with open('summary.tex', 'r', encoding='utf-8') as f:
    tex = f.read()

depth = 0
for i, c in enumerate(tex):
    if c == '{': depth += 1
    elif c == '}': depth -= 1
    if depth < 0:
        print(f'ERROR: unmatched brace at line {tex[:i].count(chr(10))+1}')
        break
if depth > 0: print(f'ERROR: {depth} unclosed braces')
elif depth == 0: print('Braces: OK')

begins = re.findall(r'\\begin\{(\w+)\}', tex)
ends = re.findall(r'\\end\{(\w+)\}', tex)
bc, ec = Counter(begins), Counter(ends)
ok = True
for env in sorted(set(list(bc.keys()) + list(ec.keys()))):
    if bc[env] != ec[env]:
        print(f'MISMATCH: {env}: {bc[env]} begins vs {ec[env]} ends')
        ok = False
if ok: print('Environments: OK')

cites = set(re.findall(r'\\cite(?:\[[^\]]*\])?\{([^}]+)\}', tex))
bibitems = set(re.findall(r'\\bibitem\{([^}]+)\}', tex))
for c in cites - bibitems: print(f'MISSING bibitem: {c}')
for b in bibitems - cites: print(f'UNCITED: {b}')
print(f'Citations: {len(cites)} cited, {len(bibitems)} in bib')
print(f'Lines: {tex.count(chr(10)) + 1}')
