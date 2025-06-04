import streamlit as st
import PyPDF2
import io
from pathlib import Path
import base64
import re
import requests
import urllib.parse
import time
from collections import defaultdict
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Any
import json

# Set page config
st.set_page_config(
    page_title="PDF Content Extractor",
    page_icon="📄",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
        .stTitle {
            color: #2c3e50;
            font-size: 3rem !important;
            padding-bottom: 2rem;
        }
        .stSubheader {
            color: #34495e;
            padding-top: 1rem;
        }
        .citation-style-badge {
            display: inline-block;
            padding: 0.25em 0.6em;
            font-size: 0.875em;
            font-weight: 600;
            line-height: 1;
            text-align: center;
            white-space: nowrap;
            vertical-align: baseline;
            border-radius: 0.25rem;
            margin-left: 0.5em;
        }
        .style-apa { background-color: #007bff; color: white; }
        .style-mla { background-color: #28a745; color: white; }
        .style-chicago { background-color: #dc3545; color: white; }
        .style-ieee { background-color: #ffc107; color: black; }
        .style-acm { background-color: #17a2b8; color: white; }
        .style-unknown { background-color: #6c757d; color: white; }
    </style>
""", unsafe_allow_html=True)

@dataclass
class CitationStyle:
    """Represents a citation style with its patterns and characteristics."""
    name: str
    patterns: List[str]
    year_pattern: str
    author_pattern: str
    title_indicators: List[str]
    common_punctuation: Dict[str, str]

# Define citation style patterns
CITATION_STYLES = {
    'APA': CitationStyle(
        name='APA',
        patterns = [
            # Author, A. A., & Author, B. B. (Year). Title. Publisher.
            r'^[A-Z][a-z]+,\s+[A-Z]\.\s*(?:[A-Z]\.\s*)?(?:,?\s*&\s*[A-Z][a-z]+,\s+[A-Z]\.\s*(?:[A-Z]\.\s*)?)?\s*\(\d{4}\)',
            # Author, A. A. (Year). Title of article. Journal Name, volume(issue), pages.
            r'^[A-Z][a-z]+,\s+[A-Z]\.\s*(?:[A-Z]\.\s*)?\s*\(\d{4}\).*?\.\s*[A-Z][a-z]+.*?,\s*\d+\s*\(\d+\),\s*\d+[-–]\d+',
            # Multiple authors with et al.
            r'^[A-Z][a-z]+,\s+[A-Z]\.\s*(?:[A-Z]\.\s*)?,\s*et\s+al\.\s*\(\d{4}\)'
        ],
        year_pattern=r'\(\d{4}\)',
        author_pattern=r'^[A-Z][a-z]+,\s+[A-Z]\.',
        title_indicators=['Italics after year', 'Sentence case'],
        common_punctuation={'after_year': '.', 'after_title': '.', 'before_pages': ','}
    ),
    
    'MLA': CitationStyle(
        name='MLA',
        patterns = [
            # Author, First. "Title." Source, vol. #, no. #, Year, pp. ##-##.
            r'^[A-Z][a-z]+,\s+[A-Z][a-z]+\.\s*"[^"]+\."\s*[A-Z][a-z]+.*?,\s*vol\.\s*\d+',
            # Author, First. Title. Publisher, Year.
            r'^[A-Z][a-z]+,\s+[A-Z][a-z]+\.\s*[A-Z][a-z]+.*?\.\s*[A-Z][a-z]+.*?,\s*\d{4}',
            # Multiple authors: Author, First, and Second Author.
            r'^[A-Z][a-z]+,\s+[A-Z][a-z]+,\s+and\s+[A-Z][a-z]+\s+[A-Z][a-z]+'
        ],
        year_pattern=r',\s*\d{4}(?:\.|,)',
        author_pattern=r'^[A-Z][a-z]+,\s+[A-Z][a-z]+',
        title_indicators=['Quotes for articles', 'Italics for books'],
        common_punctuation={'after_author': '.', 'after_title': '.', 'before_year': ','}
    ),
    
    'Chicago': CitationStyle(
        name='Chicago',
        patterns = [
            # Author, First. "Article Title." Journal Name vol. #, no. # (Year): pages.
            r'^[A-Z][a-z]+,\s+[A-Z][a-z]+\.\s*"[^"]+\."\s*[A-Z][a-z]+.*?\s+\d+,\s*no\.\s*\d+\s*\(\d{4}\):',
            # Author, First. Book Title. City: Publisher, Year.
            r'^[A-Z][a-z]+,\s+[A-Z][a-z]+\.\s*[A-Z][a-z]+.*?\.\s*[A-Z][a-z]+:\s*[A-Z][a-z]+,\s*\d{4}',
            # Footnote style: 1. Author, Title (City: Publisher, Year), page.
            r'^\d+\.\s*[A-Z][a-z]+,\s*[A-Z][a-z]+.*?\s*\([A-Z][a-z]+:\s*[A-Z][a-z]+,\s*\d{4}\)'
        ],
        year_pattern=r'\(\d{4}\)|\,\s*\d{4}(?:\.|,)',
        author_pattern=r'^(?:\d+\.\s*)?[A-Z][a-z]+,\s+[A-Z][a-z]+',
        title_indicators=['Quotes for articles', 'Italics for books', 'Footnote numbers'],
        common_punctuation={'after_author': '.', 'after_title': '.', 'publisher_separator': ':'}
    ),
    
    'IEEE': CitationStyle(
        name='IEEE',
        patterns = [
            # [1] A. Author and B. Author, "Title," Journal, vol. #, no. #, pp. ##-##, Year.
            r'^\[\d+\]\s*[A-Z]\.\s*[A-Z][a-z]+(?:\s+and\s+[A-Z]\.\s*[A-Z][a-z]+)*,\s*"[^"]+,"',
            # [1] A. Author, Title. City: Publisher, Year.
            r'^\[\d+\]\s*[A-Z]\.\s*[A-Z][a-z]+,\s*[A-Z][a-z]+.*?\.\s*[A-Z][a-z]+:\s*[A-Z][a-z]+,\s*\d{4}',
            # Conference papers
            r'^\[\d+\]\s*[A-Z]\.\s*[A-Z][a-z]+.*?,\s*"[^"]+,"\s*in\s+Proc\.'
        ],
        year_pattern=r',\s*\d{4}(?:\.|,)',
        author_pattern=r'^\[\d+\]\s*[A-Z]\.\s*[A-Z][a-z]+',
        title_indicators=['Quotes for all titles', 'Numbered references', 'Abbreviated first names'],
        common_punctuation={'after_number': ' ', 'after_authors': ',', 'title_quotes': '"'}
    ),
    
    'ACM': CitationStyle(
        name='ACM',
        patterns = [
            # [1] Patricia S. Abril and Robert Plant. 2007. Title. Journal 50, 1 (Jan. 2007), 36-44.
            r'^\[\d+\]\s*[A-Z][a-z]+\s+(?:[A-Z]\.\s+)?[A-Z][a-z]+(?:\s+and\s+[A-Z][a-z]+\s+(?:[A-Z]\.\s+)?[A-Z][a-z]+)*\.\s+\d{4}\.',
            # Full names format: First Last and First Last. Year.
            r'^(?:\[\d+\]\s*)?[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+and\s+[A-Z][a-z]+\s+[A-Z][a-z]+)*\.\s+\d{4}\.',
            # Et al. format: Author et al. Year.
            r'^(?:\[\d+\]\s*)?[A-Z][a-z]+\s+[A-Z][a-z]+,?\s+et\s+al\.\s+\d{4}\.',
            # Journal with volume, issue: Commun. ACM 50, 1 (Jan. 2007), 36-44
            r'[A-Z][a-z]+\.?\s+[A-Z]+\s+\d+,\s*\d+\s*\([A-Z][a-z]+\.?\s+\d{4}\),\s*\d+[-–]\d+',
            # Conference proceedings: In Proceedings of... (CONF 'YY)
            r'In\s+Proceedings\s+of\s+(?:the\s+)?\d*(?:st|nd|rd|th)?\.?\s*[A-Z]',
            # Article enumeration: Article 5 (April 2007), 50 pages
            r'Article\s+\d+\s*\([A-Z][a-z]+\s+\d{4}\),\s*\d+\s+pages?'
        ],
        year_pattern=r'\b\d{4}\b(?:\.|,|\s|$)',
        author_pattern=r'^(?:\[\d+\]\s*)?[A-Z][a-z]+\s+(?:[A-Z]\.\s+)?[A-Z][a-z]+',
        title_indicators=['Full names preferred', 'Year follows authors with period', 'Square brackets for numbers', 'DOI/URL at end', 'Month in parentheses for journals'],
        common_punctuation={'after_year': '.', 'between_authors': ' and ', 'after_title': '.', 'ref_brackets': '[]', 'page_separator': ', '}
    )
    
}

def detect_citation_style(reference: str) -> Tuple[str, float]:
    """
    Detect the citation style of a reference.
    Returns tuple of (style_name, confidence_score)
    """
    reference = reference.strip()
    best_match = ('Unknown', 0.0)
    
    for style_name, style in CITATION_STYLES.items():
        score = 0.0
        max_score = len(style.patterns) + 3  # patterns + year + author + punctuation
        
        # Check patterns
        for pattern in style.patterns:
            if re.search(pattern, reference, re.IGNORECASE):
                score += 1
                break
        
        # Check year pattern
        if re.search(style.year_pattern, reference):
            score += 1
        
        # Check author pattern
        if re.search(style.author_pattern, reference):
            score += 1
        
        # Check common punctuation
        punct_matches = 0
        for key, punct in style.common_punctuation.items():
            if punct in reference:
                punct_matches += 1
        score += punct_matches / len(style.common_punctuation)
        
        # Calculate confidence
        confidence = score / max_score
        if confidence > best_match[1]:
            best_match = (style_name, confidence)
    
    # If confidence is too low, return Unknown
    if best_match[1] < 0.3:
        return ('Unknown', 0.0)
    
    return best_match

def extract_reference_components(reference: str, style: str) -> Dict[str, str]:
    """Extract components like authors, title, year, etc. based on citation style."""
    components = {
        'authors': '',
        'year': '',
        'title': '',
        'source': '',
        'volume': '',
        'issue': '',
        'pages': '',
        'doi': '',
        'url': '',
        'publisher': '',
        'location': ''
    }
    
    # Extract DOI if present
    doi_match = re.search(r'(?:doi:?\s*|https?://doi\.org/)(10\.\d{4,}/[^\s,]+)', reference, re.IGNORECASE)
    if doi_match:
        components['doi'] = doi_match.group(1)
    
    # Extract URL if present
    url_match = re.search(r'https?://[^\s<>"\']+', reference)
    if url_match:
        components['url'] = url_match.group(0)
    
    # Style-specific extraction
    if style == 'APA':
        # Extract authors (before year)
        author_match = re.match(r'^([^(]+)\s*\(\d{4}\)', reference)
        if author_match:
            components['authors'] = author_match.group(1).strip()
        
        # Extract year
        year_match = re.search(r'\((\d{4})\)', reference)
        if year_match:
            components['year'] = year_match.group(1)
        
        # Extract title (after year, before next period)
        title_match = re.search(r'\(\d{4}\)\.\s*([^.]+)\.', reference)
        if title_match:
            components['title'] = title_match.group(1).strip()
    
    elif style == 'IEEE':
        # Extract reference number
        num_match = re.match(r'^\[(\d+)\]', reference)
        
        # Extract authors (after number, before comma and quotes)
        author_match = re.search(r'^\[\d+\]\s*([^,"]+),\s*"', reference)
        if author_match:
            components['authors'] = author_match.group(1).strip()
        
        # Extract title (in quotes)
        title_match = re.search(r'"([^"]+)"', reference)
        if title_match:
            components['title'] = title_match.group(1).strip()
        
        # Extract year (usually at the end)
        year_match = re.search(r',\s*(\d{4})(?:\.|,|$)', reference)
        if year_match:
            components['year'] = year_match.group(1)
    
    elif style == 'MLA':
        # Extract authors (before first period)
        author_match = re.match(r'^([^.]+)\.', reference)
        if author_match:
            components['authors'] = author_match.group(1).strip()
        
        # Extract title (in quotes or italics)
        title_match = re.search(r'[.]\s*"([^"]+)"', reference) or re.search(r'[.]\s*([^.]+)\.', reference)
        if title_match:
            components['title'] = title_match.group(1).strip()
        
        # Extract year
        year_match = re.search(r',\s*(\d{4})(?:\.|,|$)', reference)
        if year_match:
            components['year'] = year_match.group(1)
    
    elif style == 'ACM':
        # Extract reference number if present
        num_match = re.match(r'^\[(\d+)\]\s*', reference)
        ref_start = num_match.end() if num_match else 0
        
        # Extract authors and year (ACM format: Authors. Year.)
        author_year_match = re.search(r'^(?:\[\d+\]\s*)?([^.]+\.)?\s*(\d{4})\.', reference)
        if author_year_match:
            components['authors'] = author_year_match.group(1).strip('.').strip() if author_year_match.group(1) else ''
            components['year'] = author_year_match.group(2)
            
            # Extract title (after year, before next major punctuation)
            title_start = author_year_match.end()
            # Look for title ending patterns
            title_patterns = [
                r'([^.]+)\.\s*(?:In\s+Proceedings|In\s+ACM|Commun\.|J\.|Trans\.)',  # Conference/Journal
                r'([^.]+)\.\s*\(',  # Before edition info
                r'([^.]+)\.\s*[A-Z][a-z]+(?:,\s*[A-Z][a-z]+)*(?:\.|,)',  # Before publisher
                r'([^.]+)\.'  # Default: next period
            ]
            
            for pattern in title_patterns:
                title_match = re.search(pattern, reference[title_start:])
                if title_match:
                    components['title'] = title_match.group(1).strip()
                    break
        
        # Extract journal/conference info
        if 'In Proceedings of' in reference:
            proc_match = re.search(r'In Proceedings of ([^(]+)\s*\(([^)]+)\)', reference)
            if proc_match:
                components['source'] = proc_match.group(1).strip()
        else:
            # Look for journal pattern: Journal Name Vol, Issue (Month Year), pages
            journal_match = re.search(r'([A-Z][^,]+)\s+(\d+),\s*(\d+)\s*\(([^)]+)\),\s*([\d\-–]+)', reference)
            if journal_match:
                components['source'] = journal_match.group(1).strip()
                components['volume'] = journal_match.group(2)
                components['issue'] = journal_match.group(3)
                components['pages'] = journal_match.group(5)
        
        # Extract publisher and location
        publisher_match = re.search(r'([A-Z][^,]+),\s+([A-Z][^,.]+(?:,\s*[A-Z]{2})?)(?:\.|$)', reference)
        if publisher_match and 'In Proceedings' not in reference[:publisher_match.start()]:
            components['publisher'] = publisher_match.group(1).strip()
            components['location'] = publisher_match.group(2).strip()
    
    # Extract volume, issue, pages (common patterns)
    if not components['volume']:
        volume_match = re.search(r'(?:vol\.|volume)\s*(\d+)', reference, re.IGNORECASE)
        if volume_match:
            components['volume'] = volume_match.group(1)
    
    if not components['issue']:
        issue_match = re.search(r'(?:no\.|issue)\s*(\d+)|\((\d+)\)', reference, re.IGNORECASE)
        if issue_match:
            components['issue'] = issue_match.group(1) or issue_match.group(2)
    
    if not components['pages']:
        pages_match = re.search(r'(?:pp?\.|pages?)\s*(\d+[-–]\d+)|(\d+[-–]\d+)(?:\.|,|$)', reference)
        if pages_match:
            components['pages'] = pages_match.group(1) or pages_match.group(2)
    
    return components

def validate_citation_format(reference: str, style: str) -> Dict[str, Any]:
    """Validate if a citation follows the rules of a specific style."""
    validation = {
        'is_valid': True,
        'errors': [],
        'warnings': [],
        'suggestions': []
    }
    
    components = extract_reference_components(reference, style)
    style_obj = CITATION_STYLES.get(style)
    
    if not style_obj:
        validation['is_valid'] = False
        validation['errors'].append(f"Unknown citation style: {style}")
        return validation
    
    # Common validations
    if not components['authors']:
        validation['errors'].append("Missing author information")
        validation['is_valid'] = False
    
    if not components['year']:
        validation['errors'].append("Missing publication year")
        validation['is_valid'] = False
    elif not re.match(r'^\d{4}$', components['year']):
        validation['errors'].append(f"Invalid year format: {components['year']}")
        validation['is_valid'] = False
    
    if not components['title']:
        validation['errors'].append("Missing title")
        validation['is_valid'] = False
    
    # Style-specific validations
    if style == 'APA':
        # Check author format: Last, F. F.
        if components['authors'] and not re.search(r'[A-Z][a-z]+,\s+[A-Z]\.', components['authors']):
            validation['warnings'].append("APA style requires: LastName, F. M. format for authors")
        
        # Check if year is in parentheses
        if components['year'] and not re.search(rf'\({components["year"]}\)', reference):
            validation['errors'].append("APA style requires year in parentheses")
            validation['is_valid'] = False
    
    elif style == 'IEEE':
        # Check for reference number
        if not re.match(r'^\[\d+\]', reference):
            validation['errors'].append("IEEE style requires numbered references [#]")
            validation['is_valid'] = False
        
        # Check for quoted titles
        if components['title'] and '"' + components['title'] + '"' not in reference:
            validation['warnings'].append("IEEE style typically uses quotes around titles")
    
    elif style == 'MLA':
        # Check author format: Last, First
        if components['authors'] and not re.search(r'[A-Z][a-z]+,\s+[A-Z][a-z]+', components['authors']):
            validation['warnings'].append("MLA style prefers: LastName, FirstName format")
        
        # Check for proper punctuation
        if reference.count('"') % 2 != 0:
            validation['errors'].append("Unmatched quotes in citation")
            validation['is_valid'] = False
    
    elif style == 'ACM':
        # Check for reference number (optional but common)
        has_number = re.match(r'^\[\d+\]', reference)
        
        # Check author format: ACM prefers full names (First Last)
        if components['authors']:
            # Check if using initials instead of full names
            if re.search(r'\b[A-Z]\.\s*(?:[A-Z]\.\s*)?[A-Z][a-z]+', components['authors']):
                validation['warnings'].append("ACM prefers full names (e.g., 'Patricia S. Abril') over initials")
            
            # Check for 'and' between authors (not comma)
            if ',' in components['authors'] and ' and ' not in components['authors']:
                validation['warnings'].append("ACM uses 'and' between authors, not commas")
        
        # Check year format: should be followed by a period
        if components['year'] and not re.search(rf'{components["year"]}\.', reference):
            validation['errors'].append("ACM style requires period after year")
            validation['is_valid'] = False
        
        # Check for proper journal format if it's a journal article
        if re.search(r'[A-Z][a-z]+\.?\s+[A-Z]+\s+\d+,\s*\d+', reference):
            # It's likely a journal - check for month/year in parentheses
            if not re.search(r'\([A-Z][a-z]+\.?\s+\d{4}\)', reference):
                validation['warnings'].append("ACM journal citations should include month and year in parentheses: (Jan. 2007)")
        
        # Check for DOI/URL at the end
        if not (components['doi'] or components['url']):
            validation['warnings'].append("ACM style encourages including DOI or URL at the end of citations")
        
        # For conference papers, check "In Proceedings of" format
        if 'proceedings' in reference.lower() and 'In Proceedings of' not in reference:
            validation['warnings'].append("Conference papers should use 'In Proceedings of...' format")
    
    # Add suggestions based on errors
    if validation['errors']:
        validation['suggestions'].append(f"Review {style} citation guidelines")
        validation['suggestions'].append("Consider using a citation generator or manager")
    
    if style == 'ACM' and validation['warnings']:
        validation['suggestions'].append("Refer to ACM's official style guide: http://www.acm.org/publications/authors/reference-formatting")
    
    return validation

def format_style_confidence(style: str, confidence: float) -> str:
    """Format the style detection result with confidence level."""
    if style == 'Unknown':
        return '<span class="citation-style-badge style-unknown">Unknown Style</span>'
    
    confidence_text = ""
    if confidence >= 0.8:
        confidence_text = "High confidence"
    elif confidence >= 0.5:
        confidence_text = "Medium confidence"
    else:
        confidence_text = "Low confidence"
    
    style_class = f"style-{style.lower()}"
    return f'<span class="citation-style-badge {style_class}">{style} ({confidence:.0%} {confidence_text})</span>'

# Main title with emoji
st.title("📄 PDF Content Extractor with Citation Analysis")

# Add description
st.markdown("""
    Upload your PDF file and extract its content. The tool will:
    - Extract text from all pages
    - Detect and validate references with citation style analysis
    - Check if citations follow academic formats (APA, MLA, Chicago, IEEE, ACM)
    - Allow you to download the extracted text and analyzed references
""")

# Create two columns
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### Upload PDF")
    # File uploader widget with error handling
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

# Continue with the existing extraction functions...
def extract_doi_from_url(url):
    """Extract DOI from a URL if present."""
    url = re.sub(r'\s+', '', url)
    
    doi_patterns = [
        r'10\.\d{4,}/[-._;()/:\w]+',
        r'doi\.org/10\.\d{4,}/[-._;()/:\w]+',
        r'dx\.doi\.org/10\.\d{4,}/[-._;()/:\w]+',
        r'doi/(?:abs|pdf|full|book|citation)?/?10\.\d{4,}/[-._;()/:\w]+',
    ]
    
    for pattern in doi_patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            doi = match.group(0)
            if '/' in doi and '10.' in doi:
                doi = doi[doi.index('10.'):]
            return doi.strip()
    return None

def extract_urls_from_text(text):
    """Extract potential URLs from text, handling broken or spaced URLs."""
    url_pattern = r'(?:https?://|www\.)[^\s<>"\']+(?:\s+[^\s<>"\']+)*'
    
    potential_urls = []
    for match in re.finditer(url_pattern, text, re.IGNORECASE):
        url = match.group(0)
        cleaned_url = clean_url(url)
        if cleaned_url:
            potential_urls.append(cleaned_url)
    return potential_urls

def clean_url(url):
    """Clean and encode URL properly, handling spaces and special characters."""
    if not url:
        return None

    try:
        url = url.strip()
        
        url_parts = url.split()
        if len(url_parts) > 1:
            cleaned_parts = []
            for part in url_parts:
                part = re.sub(r'["\'\[\]<>{}]', '', part)
                part = part.strip('.,;:()[]{}')
                if part:
                    cleaned_parts.append(part)
            url = ''.join(cleaned_parts)
        
        url = re.sub(r'\s+', '', url)
        url = url.replace('\\', '/')
        
        if 'doi' in url.lower():
            doi = extract_doi_from_url(url)
            if doi:
                clean_doi = doi.strip().replace(' ', '')
                if 'dl.acm.org' in url.lower():
                    return f"https://dl.acm.org/doi/{clean_doi}"
                return f"https://doi.org/{clean_doi}"
        
        url = re.sub(r'[.,;:)\]}]+$', '', url)
        
        if not url.lower().startswith(('http://', 'https://')):
            if url.lower().startswith('www.'):
                url = 'https://' + url
            else:
                return None
        
        parsed = urllib.parse.urlparse(url)
        
        path_parts = parsed.path.split('/')
        cleaned_path_parts = []
        for part in path_parts:
            part = re.sub(r'["\'\[\]<>{}]', '', part)
            if part:
                cleaned_path_parts.append(urllib.parse.quote(part))
        clean_path = '/'.join(cleaned_path_parts)
        
        if parsed.query:
            query_parts = parsed.query.split('&')
            cleaned_query_parts = []
            for part in query_parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    cleaned_query_parts.append(
                        f"{urllib.parse.quote_plus(key)}={urllib.parse.quote_plus(value)}"
                    )
            clean_query = '&'.join(cleaned_query_parts)
        else:
            clean_query = ''
        
        clean_fragment = urllib.parse.quote(parsed.fragment)
        
        cleaned = parsed._replace(
            path=clean_path,
            query=clean_query,
            fragment=clean_fragment
        )
        
        final_url = urllib.parse.urlunparse(cleaned)
        
        if not re.match(r'https?://.+\..+', final_url):
            return None
        
        return final_url
    except Exception as e:
        print(f"Error cleaning URL: {str(e)}")
        return None

def is_valid_acm_url_format(url):
    """Check if URL follows valid ACM Digital Library format."""
    acm_patterns = [
        r'dl\.acm\.org/doi/(?:abs/|pdf/|)10\.\d+/[\d.]+',
        r'dl\.acm\.org/citation\.cfm\?id=\d+',
    ]
    return any(re.search(pattern, url, re.IGNORECASE) for pattern in acm_patterns)

def validate_reference(ref):
    """Validate a reference by checking various sources."""
    results = {
        'valid': False,
        'doi_found': False,
        'url_found': False,
        'scholar_search': None,
        'message': '',
        'rate_limited': False,
        'acm_url': False
    }
    
    urls = extract_urls_from_text(ref)
    for url in urls:
        if url:
            results['url_found'] = True
            
            if 'dl.acm.org' in url:
                results['acm_url'] = True
                if is_valid_acm_url_format(url):
                    results['valid'] = True
                    results['message'] = f"✅ Valid ACM Digital Library URL: {url}"
                    return results
            
            validation_result = validate_url_with_fallback(url)
            if validation_result is None:
                results['rate_limited'] = True
                results['message'] = f"⚠️ Rate limit reached, skipped validation for: {url}"
            elif validation_result:
                results['valid'] = True
                results['message'] = f"✅ Valid URL found: {url}"
                return results
    
    if not results['valid']:
        doi_match = re.search(r'(?i)doi:?\s*(10\.\d{4,}/[^\s,]+)', ref)
        if doi_match:
            doi = doi_match.group(1)
            results['doi_found'] = True
            if validate_doi(doi):
                results['valid'] = True
                results['message'] = f"✅ Valid DOI found: {doi}"
                return results
    
    search_query = urllib.parse.quote(ref[:200])
    results['scholar_search'] = f"https://scholar.google.com/scholar?q={search_query}"
    
    if not results['valid']:
        results['message'] = f"ℹ️ Reference needs manual verification: {ref}"
    
    return results

def extract_references_enhanced(text):
    """Enhanced reference extraction with multiple citation format support."""
    found_refs = []
    
    lines = text.split('\n')
    references_section = False
    references_text = ""
    start_idx = 0
    
    ref_headers = ['references', 'bibliography', 'works cited', 'literature cited', 'cited works', 'sources']
    
    for i, line in enumerate(lines):
        if any(header in line.lower() for header in ref_headers):
            references_section = True
            start_idx = i
            references_text = '\n'.join(lines[i:])
            break
    
    if not references_section:
        return []
    
    current_ref = []
    in_reference = False
    
    # Enhanced patterns for different citation styles
    ref_patterns = [
        # Numbered references [1], 1., (1)
        r'^\s*\[\d+\]',
        r'^\s*\d+\.',
        r'^\s*\(\d+\)',
        # Author-based patterns
        r'^[A-Z][a-zA-Z\-]+,?\s+(?:et\s+al\.?\s+)?(?:[A-Z]\.\s*)?(?:[A-Z]\.\s*)?\s*(?:\(\d{4}\)|,?\s*\d{4})',
        r'^[A-Z][a-zA-Z\-]+,\s*[A-Z][a-zA-Z\-]+',
        # DOI pattern
        r'^doi:',
        # URL pattern
        r'^https?://',
        # Chicago footnote style
        r'^\s*\d+\.\s*[A-Z]'
    ]
    
    for line in lines[start_idx + 1:]:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        # Check if this line starts a new reference
        is_new_ref = any(re.match(pattern, line_stripped) for pattern in ref_patterns)
        
        if is_new_ref:
            if current_ref:
                complete_ref = ' '.join(current_ref)
                if len(complete_ref) > 20:
                    found_refs.append(complete_ref)
            current_ref = [line_stripped]
            in_reference = True
        elif in_reference:
            # Check if this is a continuation (doesn't start with uppercase after period)
            if not re.match(r'^[A-Z]', line_stripped) or (current_ref and not current_ref[-1].endswith('.')):
                current_ref.append(line_stripped)
            else:
                # This might be a new paragraph/section
                if len(' '.join(current_ref)) > 50:  # Reasonable reference length
                    complete_ref = ' '.join(current_ref)
                    found_refs.append(complete_ref)
                    current_ref = []
                    in_reference = False
    
    # Add the last reference
    if current_ref and len(' '.join(current_ref)) > 20:
        complete_ref = ' '.join(current_ref)
        found_refs.append(complete_ref)
    
    return found_refs

# Rate limiting setup
RATE_LIMITS = {
    'dl.acm.org': {'requests': 0, 'last_reset': datetime.now(), 'max_requests': 10, 'reset_interval': 60},
    'doi.org': {'requests': 0, 'last_reset': datetime.now(), 'max_requests': 30, 'reset_interval': 60},
    'default': {'requests': 0, 'last_reset': datetime.now(), 'max_requests': 50, 'reset_interval': 60}
}

def check_rate_limit(domain):
    """Check if we've hit rate limit for a domain."""
    now = datetime.now()
    rate_info = RATE_LIMITS.get(domain, RATE_LIMITS['default'])
    
    if (now - rate_info['last_reset']).total_seconds() > rate_info['reset_interval']:
        rate_info['requests'] = 0
        rate_info['last_reset'] = now
    
    if rate_info['requests'] >= rate_info['max_requests']:
        return False
    
    rate_info['requests'] += 1
    return True

def get_domain(url):
    """Extract domain from URL."""
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except:
        return None

def clean_doi(doi):
    """Clean DOI and handle special characters."""
    if not doi:
        return None
    
    doi = doi.lower().strip()
    for prefix in ['doi:', 'https://doi.org/', 'http://doi.org/', 'dx.doi.org/']:
        if doi.startswith(prefix):
            doi = doi[len(prefix):].strip()
    
    doi = ''.join(doi.split())
    doi = doi.rstrip('.,;')
    
    doi_match = re.search(r'(10\.\d{4,}/[-._;()/:\w]+)', doi)
    if doi_match:
        doi = doi_match.group(1)
    
    return doi

def validate_doi(doi):
    """Validate a DOI by checking if it resolves."""
    if not doi:
        return False
    
    doi = clean_doi(doi)
    if not doi:
        return False
    
    try:
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(
            f'https://doi.org/{doi}',
            headers=headers,
            allow_redirects=True,
            timeout=5
        )
        return response.status_code == 200
    except Exception as e:
        print(f"DOI validation error: {str(e)}")
        return False

def validate_url_with_fallback(url):
    """Validate URL with fallback options and rate limiting."""
    if not url:
        return False
    
    url = clean_url(url)
    if not url:
        return False
    
    if 'dl.acm.org' in url:
        if is_valid_acm_url_format(url):
            return True
        return False
    
    doi = extract_doi_from_url(url)
    if doi:
        return validate_doi(doi)
    
    domain = get_domain(url)
    if not domain:
        return False
    
    if not check_rate_limit(domain):
        print(f"Rate limit reached for {domain}")
        return None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        response = requests.head(url, allow_redirects=True, timeout=5, headers=headers)
        
        if response.status_code in [403, 405, 406]:
            response = requests.get(
                url,
                allow_redirects=True,
                timeout=5,
                headers=headers,
                stream=True
            )
            response.close()
        
        return response.status_code == 200
    except Exception as e:
        print(f"URL validation error for {domain}: {str(e)}")
        return False

def display_reference_with_style(ref, validation_result, style_info, ref_type="standard"):
    """Display reference with both validation status and citation style analysis."""
    style, confidence = style_info
    
    # Display the reference text
    st.markdown(f"**Reference:** {ref}")
    
    # Display citation style detection
    st.markdown(format_style_confidence(style, confidence), unsafe_allow_html=True)
    
    # If style is detected, validate format
    if style != 'Unknown':
        format_validation = validate_citation_format(ref, style)
        
        # Display format validation results
        if format_validation['errors']:
            st.error("**Format Errors:**")
            for error in format_validation['errors']:
                st.markdown(f"- ❌ {error}")
        
        if format_validation['warnings']:
            st.warning("**Format Warnings:**")
            for warning in format_validation['warnings']:
                st.markdown(f"- ⚠️ {warning}")
        
        if format_validation['suggestions']:
            st.info("**Suggestions:**")
            for suggestion in format_validation['suggestions']:
                st.markdown(f"- 💡 {suggestion}")
        
        # Extract and display components
        components = extract_reference_components(ref, style)
        if any(components.values()):
            with st.expander("📋 Extracted Components"):
                cols = st.columns(2)
                with cols[0]:
                    if components['authors']:
                        st.markdown(f"**Authors:** {components['authors']}")
                    if components['year']:
                        st.markdown(f"**Year:** {components['year']}")
                    if components['title']:
                        st.markdown(f"**Title:** {components['title']}")
                with cols[1]:
                    if components['source']:
                        st.markdown(f"**Source:** {components['source']}")
                    if components['volume']:
                        st.markdown(f"**Volume:** {components['volume']}")
                    if components['pages']:
                        st.markdown(f"**Pages:** {components['pages']}")
    
    # Display URL/DOI validation status
    if validation_result['rate_limited']:
        st.warning(f"⚠️ {validation_result['message']}")
        if validation_result['scholar_search']:
            st.markdown(f"[🔍 Verify on Google Scholar]({validation_result['scholar_search']})")
    elif validation_result['valid']:
        st.success("✅ Valid Reference (URL/DOI verified)")
    else:
        if ref_type == "url":
            st.error("❌ URL not accessible")
            if validation_result['scholar_search']:
                st.markdown("**Alternative Verification Methods:**")
                st.markdown(f"1. [🔍 Verify on Google Scholar]({validation_result['scholar_search']})")
                encoded_url = urllib.parse.quote(ref)
                wayback_url = f"https://web.archive.org/web/*/{encoded_url}"
                st.markdown(f"2. [📚 Check Web Archive]({wayback_url})")
        elif ref_type == "doi":
            st.error("❌ Invalid DOI")
            if validation_result['scholar_search']:
                st.markdown(f"[🔍 Verify on Google Scholar]({validation_result['scholar_search']})")
        else:
            st.info(f"[🔍 Verify on Google Scholar]({validation_result['scholar_search']})")

# Main content display
with col2:
    if uploaded_file is not None:
        try:
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            
            text_content = ""
            with st.spinner("Extracting text from PDF..."):
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text_content += f"\n--- Page {page_num} ---\n"
                    text_content += page.extract_text()
            
            st.success(f"Successfully extracted text from {len(pdf_reader.pages)} pages!")
            
            tab1, tab2, tab3 = st.tabs(["📝 Content", "📚 References", "📊 Citation Analysis"])
            
            with tab1:
                st.subheader("Extracted Content")
                st.text_area("PDF Content", text_content, height=400)
                
                if text_content:
                    st.download_button(
                        label="Download Extracted Text",
                        data=text_content,
                        file_name=f"{Path(uploaded_file.name).stem}_extracted.txt",
                        mime="text/plain"
                    )
                    
                    st.info(f"""
                        📊 **File Statistics**
                        - File name: {uploaded_file.name}
                        - Number of pages: {len(pdf_reader.pages)}
                        - Extracted text length: {len(text_content)} characters
                    """)
            
            with tab2:
                st.subheader("References with Style Analysis")
                
                references = extract_references_enhanced(text_content)
                
                if references:
                    st.write(f"Found {len(references)} references:")
                    
                    # Analyze citation styles
                    style_counts = defaultdict(int)
                    
                    for i, ref in enumerate(references, 1):
                        st.markdown(f"### Reference {i}")
                        
                        # Detect citation style
                        style_info = detect_citation_style(ref)
                        style_counts[style_info[0]] += 1
                        
                        # Validate reference
                        validation_result = validate_reference(ref)
                        
                        # Display with style analysis
                        display_reference_with_style(ref, validation_result, style_info)
                        st.markdown("---")
                    
                    # Style summary
                    with st.expander("📊 Citation Style Summary"):
                        st.markdown("### Detected Citation Styles")
                        for style, count in sorted(style_counts.items(), key=lambda x: x[1], reverse=True):
                            percentage = (count / len(references)) * 100
                            st.markdown(f"- **{style}**: {count} references ({percentage:.1f}%)")
                        
                        # Check for consistency
                        if len(style_counts) > 1 and style_counts['Unknown'] < len(references) * 0.5:
                            st.warning("⚠️ Multiple citation styles detected. Consider using a consistent style throughout the document.")
                    
                    # Enhanced download with style information
                    references_report = "# Reference Analysis Report\n\n"
                    references_report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    references_report += f"Total References: {len(references)}\n\n"
                    
                    references_report += "## Citation Style Summary\n"
                    for style, count in sorted(style_counts.items(), key=lambda x: x[1], reverse=True):
                        percentage = (count / len(references)) * 100
                        references_report += f"- {style}: {count} ({percentage:.1f}%)\n"
                    references_report += "\n"
                    
                    references_report += "## Detailed Reference Analysis\n\n"
                    for i, ref in enumerate(references, 1):
                        style_info = detect_citation_style(ref)
                        validation_result = validate_reference(ref)
                        
                        references_report += f"### Reference {i}\n"
                        references_report += f"**Text:** {ref}\n"
                        references_report += f"**Style:** {style_info[0]} (Confidence: {style_info[1]:.1%})\n"
                        references_report += f"**URL/DOI Valid:** {'Yes' if validation_result['valid'] else 'No'}\n"
                        
                        if style_info[0] != 'Unknown':
                            format_validation = validate_citation_format(ref, style_info[0])
                            references_report += f"**Format Valid:** {'Yes' if format_validation['is_valid'] else 'No'}\n"
                            if format_validation['errors']:
                                references_report += f"**Errors:** {', '.join(format_validation['errors'])}\n"
                        
                        references_report += "\n"
                    
                    st.download_button(
                        label="Download Reference Analysis Report",
                        data=references_report,
                        file_name=f"{Path(uploaded_file.name).stem}_reference_analysis.txt",
                        mime="text/plain"
                    )
                else:
                    st.info("No references found in the document.")
            
            with tab3:
                st.subheader("Citation Style Guidelines")
                
                # Display style guidelines
                st.markdown("### Common Academic Citation Styles")
                
                style_examples = {
                    'APA': "Lastname, F. M., & Lastname, F. M. (2023). Article title in sentence case. *Journal Name*, 10(2), 123-145. https://doi.org/10.1234/example",
                    'MLA': 'Lastname, Firstname. "Article Title in Title Case." *Journal Name*, vol. 10, no. 2, 2023, pp. 123-145.',
                    'Chicago': 'Lastname, Firstname. "Article Title in Title Case." *Journal Name* 10, no. 2 (2023): 123-145. https://doi.org/10.1234/example.',
                    'IEEE': '[1] F. M. Lastname and F. M. Lastname, "Article title in title case," *Journal Name*, vol. 10, no. 2, pp. 123-145, 2023.',
                    'ACM': '[1] Patricia S. Abril and Robert Plant. 2007. The patent holder\'s dilemma: Buy, sell, or troll? Commun. ACM 50, 1 (Jan. 2007), 36-44. https://doi.org/10.1145/1188913.1188915'
                }
                
                for style, example in style_examples.items():
                    with st.expander(f"{style} Style"):
                        st.markdown(f"**Example:**\n```\n{example}\n```")
                        st.markdown(f"**Key Features:**")
                        for feature in CITATION_STYLES[style].title_indicators:
                            st.markdown(f"- {feature}")
                
                # Add validation tips
                st.markdown("### Tips for Proper Citations")
                st.markdown("""
                - **Consistency**: Use the same citation style throughout your document
                - **Completeness**: Include all required elements (authors, year, title, source)
                - **Formatting**: Pay attention to punctuation, capitalization, and italics
                - **URLs/DOIs**: Include when available for easy verification
                - **Alphabetical Order**: Many styles require references to be alphabetically ordered
                """)
                
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
            st.warning("Please make sure you've uploaded a valid PDF file.")
    else:
        st.markdown("""
            ### Preview Area
            Upload a PDF file to see:
            - Extracted content with page numbers
            - References with citation style detection
            - Validation of URLs and DOIs
            - Citation format analysis
            - Downloadable analysis report
        """)

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: #666;'>
        Made with ❤️ using Streamlit, PyPDF2, and Citation Style Analysis
    </div>
""", unsafe_allow_html=True)
        