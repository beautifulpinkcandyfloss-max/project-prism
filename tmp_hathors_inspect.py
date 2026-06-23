import fitz
import re

path = 'raw_inputs/hathors/pdfs/The_Hathor_Material.pdf'
reader = fitz.open(path)
date_re = re.compile(r'^[A-Za-z]+ \d{1,2}, \d{4}$')
for page_num in range(min(120, len(reader))):
    page_text = reader.load_page(page_num).get_text()
    lines = page_text.splitlines()
    for i, line in enumerate(lines):
        if date_re.match(line.strip()):
            start = max(0, i-3)
            end = min(len(lines), i+4)
            print('PAGE', page_num+1, 'LINE', i+1, 'DATE', line.strip())
            print('---')
            for j in range(start, end):
                print(f'{j+1}: {lines[j]}')
            print('========================')
            if page_num > 20:
                break
    if page_num > 20:
        break
reader.close()
