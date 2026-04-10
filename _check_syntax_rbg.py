import ast, sys
try:
    ast.parse(open('ramanujan_breakthrough_generator.py', encoding='utf-8').read())
    print('SYNTAX OK')
except SyntaxError as e:
    print(f'SYNTAX ERROR at line {e.lineno}: {e.msg}')
    print(f'  text: {e.text}')
    sys.exit(1)
