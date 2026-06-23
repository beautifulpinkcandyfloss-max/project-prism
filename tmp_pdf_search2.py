import fitz

paths = [
    ('cassiopaea', 'raw_inputs/cassiopaea/pdfs/the-cassiopaea-session-transcripts.pdf'),
    ('hathors', 'raw_inputs/hathors/pdfs/The_Hathor_Material.pdf')
]

for source, path in paths:
    print('---', source, '---')
    doc = fitz.open(path)
    print('pages', len(doc))
    for page_num in range(min(8, len(doc))):
        page_text = doc.load_page(page_num).get_text()
        print(f'PAGE {page_num + 1} len={len(page_text)}')
        if source == 'cassiopaea':
            for pat in ['2.1', 'July', 'END OF SESSION', 'End of session']:
                idx = page_text.find(pat)
                if idx != -1:
                    print('  found', pat, 'at', idx)
                    print(page_text[idx:idx+300].replace('\n', '\\n'))
        else:
            for pat in ['Tom Kenyon', 'channeled through', 'channeled', 'Hathor', 'January', 'February']:
                idx = page_text.lower().find(pat.lower())
                if idx != -1:
                    print('  found', pat, 'at', idx)
                    print(page_text[idx:idx+300].replace('\n', '\\n'))
    print()  
    doc.close()
