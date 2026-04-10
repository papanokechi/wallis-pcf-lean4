"""Quick validation of V8.5 dashboard HTML."""
html = open('v8.5-live-dashboard.html', encoding='utf-8').read()
opens = html.count('<div')
closes = html.count('</div>')
print(f'<div>: {opens}, </div>: {closes}, balanced: {opens == closes}')
print(f'File size: {len(html):,} bytes')
for label in ['Paradigm Shifts', 'Evolved Patterns', 'Reality-Sync', '3-Way', 'Pattern Evolution']:
    found = label in html
    print(f'  Has "{label}": {found}')
