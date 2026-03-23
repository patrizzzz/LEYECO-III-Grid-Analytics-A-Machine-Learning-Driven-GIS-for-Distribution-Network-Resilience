import zipfile
import xml.etree.ElementTree as ET
import os

def extract_text_to_file(pptx_path, output_path):
    if not os.path.exists(pptx_path):
        print(f"File not found: {pptx_path}")
        return

    try:
        with open(output_path, 'w', encoding='utf-8') as out:
            with zipfile.ZipFile(pptx_path, 'r') as z:
                slide_files = [f for f in z.namelist() if f.startswith('ppt/slides/slide') and f.endswith('.xml')]
                slide_files.sort(key=lambda x: int(os.path.basename(x).replace('slide', '').replace('.xml', '')))
                
                for i, slide_file in enumerate(slide_files, 1):
                    out.write(f"\n--- Slide {i} ---\n")
                    with z.open(slide_file) as f:
                        tree = ET.parse(f)
                        root = tree.getroot()
                        namespaces = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
                        texts = root.findall('.//a:t', namespaces)
                        for t in texts:
                            if t.text:
                                out.write(t.text + "\n")
        print(f"Extraction successful: {output_path}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    pptx_path = r"c:\Users\Patrick\Downloads\zip file leyeco\leyeco3\leyeco3\leyeco3\data\samples\LEYECO III Grid Analytics.pptx.pptx"
    output_path = r"c:\Users\Patrick\Downloads\zip file leyeco\leyeco3\leyeco3\leyeco3\tmp\pptx_content_utf8.txt"
    extract_text_to_file(pptx_path, output_path)
