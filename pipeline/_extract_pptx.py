import sys, zipfile, re
from xml.etree import ElementTree as ET
p = r"D:\Wechat\xwechat_files\wxid_tqhcohrsdr5622_9227\msg\file\2026-06\基于临床指南的GraphRAG诊断.pptx"
z = zipfile.ZipFile(p)
slides = sorted([n for n in z.namelist() if re.match(r'ppt/slides/slide\d+\.xml$', n)],
                key=lambda n: int(re.findall(r'\d+', n)[0]))
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}t'
for i, n in enumerate(slides, 1):
    root = ET.fromstring(z.read(n))
    texts = [t.text for t in root.iter(A) if t.text and t.text.strip()]
    print(f"\n===== SLIDE {i} =====")
    print(" | ".join(texts))
print(f"\nTOTAL SLIDES: {len(slides)}")
