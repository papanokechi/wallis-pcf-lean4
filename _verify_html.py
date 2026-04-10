import re
with open('micro-laws-report.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Basic checks
assert 'const DATA = ' in html, 'Missing DATA block'
assert 'multi_context_sweep' in html, 'Missing multi_context_sweep'
assert 'retrain_with_adversarial' in html, 'Missing retrain_with_adversarial'
assert 'replication_holdout' in html, 'Missing replication_holdout'
assert 'runtime_detail' in html, 'Missing runtime_detail'
assert 'conservative_conclusion' in html, 'Missing conservative_conclusion'

# Check all section IDs are present
for sid in ['multi-ctx-sweep', 'adv-retrain', 'replication', 'runtime-detail', 'conclusion']:
    assert f'id="{sid}"' in html, f'Missing section {sid}'

# Check all rendering element IDs are present
for eid in ['multi-ctx-cards', 'multi-ctx-table', 'retrain-cards', 'retrain-strata-table', 
            'repl-cards', 'repl-verdict', 'runtime-cards', 'runtime-bars', 'conclusion-text']:
    assert f'id="{eid}"' in html, f'Missing element {eid}'

# Count opening/closing script tags
assert html.count('<script>') == html.count('</script>'), 'Mismatched script tags'

print('All checks passed!')
print(f'Total HTML size: {len(html)} chars, {html.count(chr(10))} lines')
