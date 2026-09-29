import pdfplumber
import os

base = r'c:\Users\RavindraYadav\Documents\AT\case study\Learnings-selected'
out_dir = r'c:\Users\RavindraYadav\Documents\AT\case study\lecture_texts'
os.makedirs(out_dir, exist_ok=True)

lectures = [
    ('01_ATF_Intro to Architectural Thinking_v7.2.pdf', 'lec01_intro.txt'),
    ('02_ATF_What is Architecture_v7.2.pdf', 'lec02_what_is_architecture.txt'),
    ('03_ATF_Requirements Aspect_v7.2.pdf', 'lec03_requirements.txt'),
    ('04_ATF_Architectural Decisions and Principles_v7.2.pdf', 'lec04_decisions.txt'),
    ('05_ATF_Architecture Overview_v7.2.pdf', 'lec05_overview.txt'),
    ('06_ATF_Functional Aspect_v7.2.pdf', 'lec06_functional.txt'),
    ('07_ATF_Operational Aspect_v7.2.pdf', 'lec07_operational.txt'),
    ('08_ATF_Validation and Viability_v7.2.pdf', 'lec08_validation.txt'),
    ('09_ATF_Agile for Architects_v7.2.pdf', 'lec09_agile.txt'),
    ('10_ATF_Summary and Close_v7.2.pdf', 'lec10_summary.txt'),
]

for pdf_name, out_name in lectures:
    path = os.path.join(base, pdf_name)
    try:
        with pdfplumber.open(path) as pdf:
            text = ''
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + '\n\n---PAGE---\n\n'
        with open(os.path.join(out_dir, out_name), 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"OK: {out_name} ({len(text)} chars, {len(pdf.pages)} pages)")
    except Exception as e:
        print(f"ERROR: {pdf_name}: {e}")

print("\nDone!")
