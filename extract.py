import pdfplumber
from fpdf import FPDF
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

def extract_text_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    return text

pdf_text = extract_text_from_pdf("Rares_Florea.pdf")
# print(pdf_text)

# Initialize Presidio
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

# Analyze and anonymize text
results = analyzer.analyze(text=pdf_text, entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS"], language="en")
redacted_text = anonymizer.anonymize(text=pdf_text, analyzer_results=results).text

# print(redacted_text)

# def clean_text(text):
#     # First, replace common special characters
#     replacements = {
#         '\uf0b7': '-',  # bullet point
#         '\u2022': '-',  # bullet point
#         '•': '-',       # bullet point
#         '–': '-',       # en dash
#         '—': '-',       # em dash
#         '"': '"',       # smart quotes
#         '"': '"',
#         ''': "'",
#         ''': "'",
#         '…': '...',
#         '\xa0': ' ',    # non-breaking space
#     }
    
#     # Replace special characters
#     for old, new in replacements.items():
#         text = text.replace(old, new)
    
#     # Replace any remaining non-ASCII characters
#     cleaned = ''
#     for char in text:
#         if ord(char) < 128:
#             cleaned += char
#         else:
#             cleaned += '-'
    
#     return cleaned

# def save_text_as_pdf(text, output_path):
#     pdf = FPDF(format='A4')
#     pdf.set_auto_page_break(auto=True, margin=15)
#     pdf.add_page()
    
#     # Set margins
#     pdf.add_font("DejaVu", "", "DejaVuSansCondensed.ttf")
#     pdf.set_font("DejaVu", size=12)

#     pdf.set_left_margin(20)
#     pdf.set_right_margin(20)
    
#     # Calculate effective width
#     effective_width = pdf.w - pdf.l_margin - pdf.r_margin
    
#     # Clean and process text
#     cleaned_text = clean_text(text)
#     lines = cleaned_text.split('\n')
    
#     for line in lines:
#         if line.strip():
#             pdf.multi_cell(effective_width, 5, line)
    
#     pdf.output(output_path)

def save_to_text_file(text, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)

# After redaction, save to text file
save_to_text_file(redacted_text, "redacted_resume.txt")

# Continue with PDF creation
# save_text_as_pdf(redacted_text, "redacted_resume.pdf")

