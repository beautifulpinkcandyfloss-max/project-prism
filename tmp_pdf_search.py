import fitz

for source, path in [
    ('cassiopaea', 'raw_inputs/cassiopaea/pdfs/the-cassiopaea-session-transcripts.pdf'),
    ('hathors', 'raw_inputs/hathors/pdfs/The_Hathor_Material.pdf')]:
    print('---', source, '---')
    doc = fitz.open(path)
    print('pages', len(doc))
    text = []
    for i in range(min(40, len(doc))):
        text.append(doc.load_page(i).get_text())
    full = '\n'.join(text)
    print('full len', len(full))
    if source == 'cassiopaea':
        for pat in ['2.1', '2.2', '2.3', '2.', 'JULY', 'END OF SESSION', 'END OF SESSION 2.1']:
            print('find', pat, full.find(pat))
        idx = full.find('2.1')
        if idx != -1:
            print('\n=== snippet around 2.1 ===')
            print(full[idx:idx+800])
    else:
        for pat in ['Tom Kenyon', 'channeled through', 'channeled', 'The Hathor', 'February', 'January', 'tom kenyon »', 'tom kenyon »']:
            print('find', pat, full.lower().find(pat.lower()))
        idx = full.lower().find('tom kenyon')
        if idx != -1:
            print('\n=== tom kenyon snippet ===')
            print(full[idx:idx+800])
        idx = full.lower().find('channeled through')
        if idx != -1:
            print('\n=== channeled through snippet ===')
            print(full[idx:idx+800])
    doc.close()
