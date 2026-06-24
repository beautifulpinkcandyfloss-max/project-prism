from parsers.cassiopaea import parse as parse_c
from parsers.hathors import parse as parse_h
from readers import read_pdf_file

for source, path, parser in [
    ('cassiopaea', 'raw_inputs/cassiopaea/pdfs/the-cassiopaea-session-transcripts.pdf', parse_c),
    ('hathors', 'raw_inputs/hathors/pdfs/The_Hathor_Material.pdf', parse_h),
]:
    print('---', source, '---')
    text = read_pdf_file(path)
    recs = parser(text, path)
    print('record count:', len(recs))
    if recs:
        for i, rec in enumerate(recs[:2], 1):
            print('record', i)
            print('uid=', rec.session_uid)
            print('date=', rec.date)
            print('participants=', rec.participants)
            print('text snippet=', rec.text[:300].replace('\n', '\\n'))
            print('---')
