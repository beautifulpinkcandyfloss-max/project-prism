import fitz
import re

path = 'raw_inputs/hathors/pdfs/The_Hathor_Material.pdf'
reader = fitz.open(path)
keywords = ['hathor', 'tom kenyon', 'channeled', 'message', 'chapter', 'through', 'january', 'february', 'maya', '1996', '1997']
for page_num in range(min(100, len(reader))):
    page_text = reader.load_page(page_num).get_text()
    low = page_text.lower()
    matches = [kw for kw in keywords if kw in low]
    if matches:
        print('PAGE', page_num+1, 'matches', matches)
        lines = page_text.splitlines()
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in keywords):
                start = max(0, i-3)
                end = min(len(lines), i+4)
                print('--- line', i+1, '---')
                for j in range(start, end):
                    print(f'{j+1}: {lines[j]}')
                print('====')
        print('-------------------------')
reader.close()
