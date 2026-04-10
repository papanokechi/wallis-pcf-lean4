import re, os, glob

tex_files = glob.glob('*.tex') + glob.glob('proof_ready/*.tex')
for f in sorted(tex_files):
    try:
        with open(f, 'r', encoding='utf-8') as fh:
            tex = fh.read()
    except:
        continue
    lines = tex.count('\n') + 1
    has_docclass = bool(re.search(r'\\documentclass', tex))
    has_begin = bool(re.search(r'\\begin\{document\}', tex))
    has_end = bool(re.search(r'\\end\{document\}', tex))
    has_title = bool(re.search(r'\\title', tex))
    has_author = bool(re.search(r'\\author', tex))
    has_abstract = bool(re.search(r'\\begin\{abstract\}', tex))
    has_bib = bool(re.search(r'\\bibitem|\\bibliography\{', tex))

    cites = set()
    for m in re.finditer(r'\\cite\{([^}]+)\}', tex):
        for key in m.group(1).split(','):
            cites.add(key.strip())
    bibitems = set(re.findall(r'\\bibitem\{([^}]+)\}', tex))
    dangling = cites - bibitems

    refs = set(re.findall(r'\\ref\{([^}]+)\}', tex))
    labels = set(re.findall(r'\\label\{([^}]+)\}', tex))
    dangling_refs = refs - labels

    n_thm = len(re.findall(r'\\begin\{theorem', tex))
    n_proof = len(re.findall(r'\\begin\{proof', tex))
    n_conj = len(re.findall(r'\\begin\{conjecture', tex))

    status = []
    if has_docclass and has_begin and has_end and has_title and has_author:
        status.append('COMPLETE')
    else:
        missing = []
        if not has_docclass: missing.append('docclass')
        if not has_begin: missing.append('begin')
        if not has_end: missing.append('end')
        if not has_title: missing.append('title')
        if not has_author: missing.append('author')
        status.append('INCOMPLETE:' + ','.join(missing))

    if not has_abstract: status.append('no-abstract')
    if not has_bib: status.append('no-bib')
    if dangling: status.append('dangling-cites:' + str(sorted(dangling)))
    if dangling_refs: status.append('dangling-refs:' + str(len(dangling_refs)))

    sep = ' | '
    print(f'{f} ({lines}L, {n_thm}thm/{n_proof}pf/{n_conj}conj) [{sep.join(status)}]')
