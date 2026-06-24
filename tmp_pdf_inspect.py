from pathlib import Path
import fitz

for source, path in [
    ('cassiopaea', Path('raw_inputs/cassiopaea/pdfs/the-cassiopaea-session-transcripts.pdf')),
    ('hathors', Path('raw_inputs/hathors/pdfs/The_Hathor_Material.pdf')),
]:
    print('---', source, '---')
    doc = fitz.open(path)
    print('pages', len(doc))
    for i, page in enumerate(doc[:3], 1):
        text = page.get_text()
        print(f'page {i} text length', len(text))
        print('first 300 chars:', repr(text[:300]))
    doc.close()
