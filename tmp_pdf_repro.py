import re
from readers import read_pdf_file
from parsers.cassiopaea import SESSION_HEADER_RE
from parsers.hathors import TITLE_RE, CHANNELED_THROUGH_RE

sources = [
    ('cassiopaea', 'raw_inputs/cassiopaea/pdfs/the-cassiopaea-session-transcripts.pdf', [SESSION_HEADER_RE]),
    ('hathors', 'raw_inputs/hathors/pdfs/The_Hathor_Material.pdf', [TITLE_RE, CHANNELED_THROUGH_RE]),
]
for source, path, regexes in sources:
    print('---', source, '---')
    text = read_pdf_file(path)
    print('len', len(text))
    print('first 200 chars:', repr(text[:200]))
    print('first 20 lines:')
    lines = text.splitlines()
    for i, line in enumerate(lines[:20], 1):
        print(i, repr(line))
    for regex in regexes:
        m = regex.search(text)
        print('regex', regex.pattern, 'match', bool(m), 'group1', m.group(1) if m else None)
    print()
