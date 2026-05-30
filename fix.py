import re

with open('PROJECT_GUIDE.md', 'r', encoding='utf-8') as f:
    text = f.read()

target_start = '- A **positive gap** indicates an underserved corridor (demand exceeds supply).'
target_end = '## Genetic'

start_idx = text.find(target_start)
end_idx = text.find(target_end, start_idx)

if start_idx != -1 and end_idx != -1:
    with open('insert.txt', 'r', encoding='utf-8') as f:
        insert_text = f.read()
    new_text = text[:start_idx] + target_start + insert_text + text[end_idx:]
    with open('PROJECT_GUIDE.md', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("PROJECT_GUIDE.md updated successfully.")
else:
    print("Could not find target strings in PROJECT_GUIDE.md")
