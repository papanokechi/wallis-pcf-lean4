import re, sys

tex = open('tex/pcf_unified.tex', encoding='utf-8').read()

# Check for undefined labels
labels = set(re.findall(r'\\label\{([^}]+)\}', tex))
refs = set(re.findall(r'\\(?:ref|eqref)\{([^}]+)\}', tex))
missing = refs - labels
if missing:
    print(f'MISSING labels: {missing}')
else:
    print(f'All refs have labels: {len(refs)} refs, {len(labels)} labels')

# Check bibitems vs cites
bibs = set(re.findall(r'\\bibitem\{([^}]+)\}', tex))
cites_raw = re.findall(r'\\cite\{([^}]+)\}', tex)
cites = set()
for c in cites_raw:
    for k in c.split(','):
        cites.add(k.strip())
missing_bib = cites - bibs
unused_bib = bibs - cites
if missing_bib:
    print(f'MISSING bibitems: {missing_bib}')
if unused_bib:
    print(f'Unused bibitems: {unused_bib}')
if not missing_bib and not unused_bib:
    print(f'Bibliography OK: {len(bibs)} items, all cited')

# Check for common issues
issues = []
# Undefined commands (heuristic)
custom_cmds = set(re.findall(r'\\newcommand\{\\(\w+)\}', tex))
custom_cmds.update(['PCF', 'half', 'dff', 'hyp'])
print(f'Custom commands defined: {custom_cmds}')

# Check theorem environments used vs defined
env_defs = set(re.findall(r'\\newtheorem\{(\w+)\}', tex))
envs_used = set(re.findall(r'\\begin\{(\w+)\}', tex))
theorem_envs = envs_used & {'theorem','lemma','corollary','proposition','conjecture','definition','remark'}
undef_thm = theorem_envs - env_defs
if undef_thm:
    print(f'UNDEFINED theorem envs: {undef_thm}')
else:
    print(f'Theorem environments OK: {theorem_envs}')

print('\nValidation complete.')
