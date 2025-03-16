import os
import argparse
import fitz  # PyMuPDF
from typing import List, Tuple, Set, Dict
import spacy
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from difflib import SequenceMatcher
import shutil

# Default technology terms commonly misidentified as PII
DEFAULT_IGNORE_TERMS = {
    "git", "github", "gitlab", "bitbucket",
    "python", "java", "javascript", "typescript", "c++", "c#", "ruby", "go", "rust", "php", "perl", 
    "react", "angular", "vue", "svelte", "jquery", "node", "nodejs", "express", 
    "django", "flask", "spring", "rails", "laravel", "symfony",
    "aws", "azure", "gcp", "cloud", "docker", "kubernetes", "terraform",
    "sql", "mysql", "postgresql", "mongodb", "oracle", "redis", "cassandra",
    "linux", "unix", "windows", "macos", "ubuntu", "debian", "fedora", "centos",
    "agile", "scrum", "kanban", "jira", "confluence", "trello",
    "jenkins", "circleci", "travis", "github actions", "gitlab ci", "bitbucket pipelines",
    "selenium", "cypress", "jest", "mocha", "chai", "jasmine", "pytest", "unittest",
    "docker-compose", "vagrant", "ansible", "puppet", "chef",
    "elasticsearch", "logstash", "kibana", "grafana", "prometheus",
    "mongodb", "cassandra", "hadoop", "spark", "flink",
    "redis", "memcached", "rabbitmq", "kafka", "active directory",
    "oauth", "openid", "jwt", "saml", "ldap",
    "rest", "soap", "graphql", "websocket", "http", "https",
    "tcp", "udp", "ip", "dns", "dhcp",
    "ssl", "tls", "ssh", "ftp", "sftp", "scp",
    "http2", "http3", "quic", "websocket",
    "json", "xml", "yaml", "csv", "protobuf",
    "html", "css", "scss", "less", "sass",
    "bootstrap", "tailwind", "materialize", "foundation",
    "webpack", "gulp", "grunt", "parcel", "vite",
    "babel", "typescript", "eslint", "prettier",
    "ASCII", "UTF-8", "ISO-8859-1", "UTF-16", "UTF-32",
    "ASP.NET", "PHP", "Ruby on Rails", "Django", "Flask",
    "Spring", "Laravel", "Symfony", "Express",
    "ASP.NET", "asp.net", ".net", ".NET", "dotnet", "asp", 
}

def setup_presidio():
    """Set up and return the Presidio analyzer engine."""
    # Download spaCy model if not already present
    try:
        nlp = spacy.load("en_core_web_lg")
    except OSError:
        import sys

        # print("Downloading the spaCy model...")
        os.system(f"{sys.executable} -m spacy download en_core_web_lg")
        nlp = spacy.load("en_core_web_lg")

    # Create NLP engine - use the configuration approach instead
    # This creates a default SpaCy NLP engine with the provided model
    return AnalyzerEngine(nlp_engine=None, registry=None)


def find_text_on_page(page, text: str) -> List[fitz.Rect]:
    """Find all occurrences of text on a page and return their rectangles."""
    text_instances = page.search_for(text.strip())
    return text_instances


def normalize_text(text: str) -> str:
    """Normalize text for better comparison (handle periods, special chars, etc.)"""
    # Handle common variations with periods and special chars
    return text.lower().replace(".", "").replace("-", "").replace(" ", "")

def should_ignore(entity_text: str, ignore_terms: Set[str], entity_type: str = None) -> bool:
    """Determine if an entity should be ignored based on ignore terms."""
    entity_lower = entity_text.lower()
    normalized_entity = normalize_text(entity_text)
    
    # Direct match with an ignore term
    if entity_lower in ignore_terms:
        return True
    
    # Special handling for terms with periods (like ASP.NET)
    if normalized_entity in {normalize_text(term) for term in ignore_terms}:
        return True
    
    # Check if entity is a tech term (exact word match)
    words = entity_lower.split()
    for word in words:
        if word in ignore_terms:
            return True
        # Also check normalized versions
        if normalize_text(word) in {normalize_text(term) for term in ignore_terms}:
            return True
    
    # Special case for URL entity type - additional checks for tech domain names
    if entity_type == "URL" and any(tech_term in entity_lower 
                                   for tech_term in [".net", "asp", "flask", "django", "rails"]):
        return True
    
    return False

def similar(a, b):
    """Calculate similarity ratio between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def redact_pdf(pdf_path: str, output_path: str, analyzer: AnalyzerEngine, ignore_terms: Set[str] = None):
    """Redact PII from a PDF and save the result."""
    try:
        # Initialize ignore_terms if None
        if ignore_terms is None:
            ignore_terms = set()
        
        # Combine with default ignore terms
        ignore_terms = {term.lower() for term in ignore_terms}.union(DEFAULT_IGNORE_TERMS)

        try:
            # Try to open the PDF
            pdf_document = fitz.open(pdf_path)
        except Exception as e:
            print(f"Error opening PDF {pdf_path}: {str(e)}")
            # If we can't open or repair, just copy the file
            shutil.copy2(pdf_path, output_path)
            print(f"Copied original file to {output_path} due to opening error")
            return

        # Add back ADDRESS and LOCATION for more complete PII detection
        entities_to_detect = [
            "PERSON",
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "URL",
        ]

        # Keep track of found person names for similarity detection
        found_persons = []
        
        # First pass - collect all detected entities
        all_results = []
        for page_num in range(len(pdf_document)):
            try:
                page = pdf_document[page_num]
                text = page.get_text()
                analyzer_results = analyzer.analyze(
                    text=text, entities=entities_to_detect, language="en"
                )
                
                for result in analyzer_results:
                    entity_text = text[result.start : result.end]
                    entity_type = result.entity_type
                    
                    # Skip if in ignore list
                    if should_ignore(entity_text, ignore_terms, entity_type):
                        continue
                        
                    all_results.append((page_num, result, entity_text))
                    
                    # Store person names for later similarity checking
                    if entity_type == "PERSON":
                        found_persons.append(entity_text)
            except Exception as e:
                print(f"Error processing page {page_num} of {pdf_path}: {str(e)}")
                continue
        
        # Second pass - find similar names not caught by Presidio
        name_variants = {}
        for page_num in range(len(pdf_document)):
            try:
                page = pdf_document[page_num]
                text = page.get_text()
                words = text.split()
                
                # For each word sequence, check if it's similar to any found person
                for i in range(len(words)):
                    # Check word groups of different lengths (2-4 words) for name matches
                    for name_length in range(2, 5):
                        if i + name_length <= len(words):
                            potential_name = " ".join(words[i:i+name_length])
                            
                            # Skip short potential names
                            if len(potential_name) < 8:
                                continue
                                
                            for person in found_persons:
                                # Only consider longer names to avoid false positives
                                if len(person) >= 8:
                                    similarity = similar(potential_name, person)
                                    # If very similar but not identical
                                    if similarity > 0.8 and similarity < 1.0 and potential_name.lower() != person.lower():
                                        # print(f"Found similar name variant: '{potential_name}' -> '{person}' (similarity: {similarity:.2f})")
                                        name_variants[potential_name] = True
            except Exception as e:
                print(f"Error processing page {page_num} of {pdf_path}: {str(e)}")
                continue
    
        # Process each page for redaction
        for page_num in range(len(pdf_document)):
            try:
                page = pdf_document[page_num]
                
                # Redact recognized entities
                for page_idx, result, entity_text in all_results:
                    if page_idx == page_num:
                        # print(f"Found {result.entity_type}: {entity_text}")
                        
                        # Find the text location in the PDF
                        text_instances = find_text_on_page(page, entity_text)
                        
                        # Redact by drawing black rectangles
                        for rect in text_instances:
                            rect.x0 -= 2
                            rect.y0 -= 2
                            rect.x1 += 2
                            rect.y1 += 2
                            page.add_redact_annot(rect, fill=(0, 0, 0))
                
                # Redact name variants
                for variant in name_variants:
                    # print(f"Redacting name variant: {variant}")
                    text_instances = find_text_on_page(page, variant)
                    for rect in text_instances:
                        rect.x0 -= 2
                        rect.y0 -= 2
                        rect.x1 += 2
                        rect.y1 += 2
                        page.add_redact_annot(rect, fill=(0, 0, 0))
                
                # Apply redactions
                page.apply_redactions()
            except Exception as e:
                print(f"Error applying redactions on page {page_num} of {pdf_path}: {str(e)}")
                continue

        # Save the redacted PDF
        try:
            pdf_document.save(output_path)
        except Exception as e:
            print(f"Error saving PDF {output_path}: {str(e)}")
            # If saving fails, copy the original file
            shutil.copy2(pdf_path, output_path)
            print(f"Copied original file to {output_path} due to saving error")
        finally:
            pdf_document.close()
        
        # print(f"Saved redacted PDF to {output_path}")
    except Exception as e:
        print(f"Unexpected error processing {pdf_path}: {str(e)}")
        traceback.print_exc()

def process_directory(input_dir: str, output_dir: str, analyzer: AnalyzerEngine, ignore_terms: Set[str] = None):
    """Process all PDFs in a directory."""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    count = 0
    # Process each PDF file
    for filename in os.listdir(input_dir):
        count += 1
        if filename.lower().endswith(".pdf"):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, f"{count}.pdf")
            redact_pdf(input_path, output_path, analyzer, ignore_terms)


def parse_ignore_terms(ignore_list: str) -> Set[str]:
    """Parse comma-separated ignore terms into a set."""
    if not ignore_list:
        return set()
    return {term.strip() for term in ignore_list.split(',')}


def main():
    parser = argparse.ArgumentParser(description="Redact PII from CV/resume PDFs")
    parser.add_argument(
        "--input", required=True, help="Path to PDF file or directory of PDFs"
    )
    parser.add_argument(
        "--output", required=True, help="Path for output file or directory"
    )
    parser.add_argument(
        "--batch", action="store_true", help="Process a directory of PDFs"
    )
    parser.add_argument(
        "--ignore", 
        help="Comma-separated list of additional terms to ignore (e.g., 'React,Node')"
    )
    parser.add_argument(
        "--disable-default-ignores", 
        action="store_true",
        help="Disable the default technology terms ignore list"
    )

    args = parser.parse_args()

    # Set up Presidio analyzer
    analyzer = setup_presidio()
    
    # Parse ignore terms
    ignore_terms = parse_ignore_terms(args.ignore)
    
    # If default ignores are disabled, don't include them
    # if args.disable_default_ignores:
    #     if ignore_terms:
    #         print(f"Using only custom ignore terms: {', '.join(ignore_terms)}")
    # else:
    #     print(f"Using default tech term ignore list plus {len(ignore_terms)} custom terms")

    if args.batch:
        process_directory(args.input, args.output, analyzer, ignore_terms)
    else:
        redact_pdf(args.input, args.output, analyzer, ignore_terms)


if __name__ == "__main__":
    main()
