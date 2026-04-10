"""Audit: cross-reference key results against all tex files."""
import re, os

results_checklist = [
    ('Log Ladder proved',                 r'Logarithmic Ladder'),
    ('Pi m=0 proved',                     r'Pi.*Family.*m\s*=\s*0|base case|thm:pi0|thm:pi\b'),
    ('Pi m=1 proved (P_n closed form)',   r'thm:pi-m1|thm:conv1|m\s*=\s*1.*convergent|n\^2\s*\+\s*3n\s*\+\s*1'),
    ('Polynomial boundary (m>=2)',        r'poly.*boundary|rem:poly'),
    ('Parity phenomenon',                 r'[Pp]arity'),
    ('Binomial recurrence conjecture',    r'[Bb]inomial.*[Rr]ecurrence|conj:rec|conj:ratio'),
    ('Family extended to m=20',           r'm\s*=\s*20'),
    ('Gamma function / continuous',       r'Gamma.*[Ff]unction|continuous.*family|thm:gamma'),
    ('Casoratian series identity',        r'Casoratian|discrete.*Wronskian'),
    ('482 irrational constants',          r'482'),
    ('Dichotomy principle',               r'[Dd]ichotomy'),
    ('Grand Rosetta 4-family table',      r'[Rr]osetta'),
    ('zeta(3) candidates section',        r'zeta.*3.*[Cc]andidate|sec:zeta3'),
    ('Wallis integral connection',        r'[Ww]allis.*integral'),
    ('Arb certification 1500+ digits',    r'[Aa]rb.*certif|1509|1518'),
    ('Gauss CF non-membership',           r'[Gg]auss.*CF|not.*Gauss'),
    ('Borel regularization',              r'[Bb]orel'),
    ('Brouncker CF comparison',           r'[Bb]rouncker'),
    ('OEIS A028387 link',                 r'A028387'),
]

tex_dir = r'c:\Users\shkub\OneDrive\Documents\archive\admin\VSCode\claude-chat\tex'
root_dir = r'c:\Users\shkub\OneDrive\Documents\archive\admin\VSCode\claude-chat'
files = {}
for f in os.listdir(tex_dir):
    if f.endswith('.tex'):
        files[f] = open(os.path.join(tex_dir, f), encoding='utf-8', errors='replace').read()
archive_dir = os.path.join(tex_dir, 'archive')
if os.path.isdir(archive_dir):
    for f in os.listdir(archive_dir):
        if f.endswith('.tex'):
            files[f'A/{f}'] = open(os.path.join(archive_dir, f), encoding='utf-8', errors='replace').read()
root_pcf = os.path.join(root_dir, 'pcf_paper_final.tex')
files['ROOT'] = open(root_pcf, encoding='utf-8', errors='replace').read()

# Short names
snames = list(files.keys())
print(f'{"Result":<45s}', end='')
for sn in snames:
    print(f' {sn[:14]:>14s}', end='')
print()
print('-' * (45 + 15 * len(snames)))

gaps = []
for label, pattern in results_checklist:
    print(f'{label:<45s}', end='')
    found_any = False
    for sn in snames:
        found = bool(re.search(pattern, files[sn], re.IGNORECASE))
        mark = 'Y' if found else '-'
        if found: found_any = True
        print(f' {mark:>14s}', end='')
    if not found_any:
        gaps.append(label)
    print('  MISSING!' if not found_any else '')

print()
if gaps:
    print(f'*** {len(gaps)} GAPS: results not in ANY tex file:')
    for g in gaps:
        print(f'  - {g}')
else:
    print('All key results are covered in at least one tex file.')
