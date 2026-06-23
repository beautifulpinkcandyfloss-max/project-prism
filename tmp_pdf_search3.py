import fitz

checks = [
    ('Q:', 'Q:'),
    ('A:', 'A:'),
    ('END OF SESSION', 'END OF SESSION'),
    ('The Cassiopaeans', 'The Cassiopaeans'),
    ('channeled through', 'channeled through'),
    ('Tom Kenyon', 'Tom Kenyon'),
    ('Hathor', 'Hathor'),
    ('January', 'January'),
    ('February', 'February'),
    ('December', 'December'),
    ('1997', '1997')
]

for source, path in [
    ('cassiopaea', 'raw_inputs/cassiopaea/pdfs/the-cassiopaea-session-transcripts.pdf'),
    ('hathors', 'raw_inputs/hathors/pdfs/The_Hathor_Material.pdf')]:
    print('---', source, '---')
    doc = fitz.open(path)
    print('pages', len(doc))
    found = {k: False for k, _ in checks}
    for i in range(min(200, len(doc))):
        page_text = doc.load_page(i).get_text()
        for key, pat in checks:
            if not found[key]:
                idx = page_text.lower().find(pat.lower())
                if idx != -1:
                    found[key] = True
                    snippet = page_text[max(0, idx-60):idx+240].replace('\n', '\\n')
                    print(f'PAGE {i+1} {key} at {idx}:')
                    print(snippet)
                    print('---')
        if all(found.values()):
            break
    print('found summary:', {k: found[k] for k, _ in checks})
    print()
    doc.close()
