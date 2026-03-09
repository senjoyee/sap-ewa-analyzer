import re

def test_chunking():
    markdown = """# 1. Check Overview
This is chapter 1 text. Usually skipped.

# 2. SAP Performance
This is chapter 2 text.
We have some CPU data and memory.

## 2.1 Sub-chapter
Some more text.

# 3. Security
Security findings here.
[RED] User SAP* is unlocked.

# 4. Database
DB chapter.
"""
    
    chunks = []
    pattern = re.compile(r'^(# \d+\.? .*$)', re.MULTILINE)
    matches = list(pattern.finditer(markdown))
    
    for i in range(len(matches)):
        start_idx = matches[i].start()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(markdown)
        
        chunk_text = markdown[start_idx:end_idx].strip()
        title_line = matches[i].group(1).lower()
        
        if " 1." in title_line or "# 1 " in title_line:
            if "overview" in title_line:
                print(f"Skipping: {matches[i].group(1)}")
                continue
        
        if len(chunk_text) > 10:
            chunks.append(chunk_text)
            
    print(f"Total chunks extracted: {len(chunks)}")
    for idx, c in enumerate(chunks):
        title = c.split('\n')[0]
        print(f"Chunk {idx+1}: {title} (length: {len(c)})")

if __name__ == "__main__":
    test_chunking()
