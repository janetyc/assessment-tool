"""
Enhanced PDF Citation Analyzer
A comprehensive tool for extracting and analyzing citations from academic PDFs.
"""

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

# ============================================================================
# CONFIGURATION AND CONSTANTS
# ============================================================================

# Rate limiting configuration
RATE_LIMITS = {
    'dl.acm.org': {'requests': 0, 'last_reset': datetime.now(), 'max_requests': 10, 'reset_interval': 60},
    'doi.org': {'requests': 0, 'last_reset': datetime.now(), 'max_requests': 30, 'reset_interval': 60},
    'default': {'requests': 0, 'last_reset': datetime.now(), 'max_requests': 50, 'reset_interval': 60}
}

# Set page config
st.set_page_config(
    page_title="PDF Citation Analyzer",
    page_icon="📄",
    layout="wide"
)

# ============================================================================
# CITATION STYLE DEFINITIONS
# ============================================================================

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
        patterns=[
            r'^[A-Z][a-z]+,\s+[A-Z]\.\s*(?:[A-Z]\.\s*)?(?:,?\s*&\s*[A-Z][a-z]+,\s+[A-Z]\.\s*(?:[A-Z]\.\s*)?)?\s*\(\d{4}\)',
            r'^[A-Z][a-z]+,\s+[A-Z]\.\s*(?:[A-Z]\.\s*)?\s*\(\d{4}\).*?\.\s*[A-Z][a-z]+.*?,\s*\d+\s*\(\d+\),\s*\d+[-–]\d+',
            r'^[A-Z][a-z]+,\s+[A-Z]\.\s*(?:[A-Z]\.\s*)?,\s*et\s+al\.\s*\(\d{4}\)'
        ],
        year_pattern=r'\(\d{4}\)',
        author_pattern=r'^[A-Z][a-z]+,\s+[A-Z]\.',
        title_indicators=['Italics after year', 'Sentence case'],
        common_punctuation={'after_year': '.', 'after_title': '.', 'before_pages': ','}
    ),
    
    'MLA': CitationStyle(
        name='MLA',
        patterns=[
            r'^[A-Z][a-z]+,\s+[A-Z][a-z]+\.\s*"[^"]+\."\s*[A-Z][a-z]+.*?,\s*vol\.\s*\d+',
            r'^[A-Z][a-z]+,\s+[A-Z][a-z]+\.\s*[A-Z][a-z]+.*?\.\s*[A-Z][a-z]+.*?,\s*\d{4}',
            r'^[A-Z][a-z]+,\s+[A-Z][a-z]+,\s+and\s+[A-Z][a-z]+\s+[A-Z][a-z]+'
        ],
        year_pattern=r',\s*\d{4}(?:\.|,)',
        author_pattern=r'^[A-Z][a-z]+,\s+[A-Z][a-z]+',
        title_indicators=['Quotes for articles', 'Italics for books'],
        common_punctuation={'after_author': '.', 'after_title': '.', 'before_year': ','}
    ),
    
    'Chicago': CitationStyle(
        name='Chicago',
        patterns=[
            r'^[A-Z][a-z]+,\s+[A-Z][a-z]+\.\s*"[^"]+\."\s*[A-Z][a-z]+.*?\s+\d+,\s*no\.\s*\d+\s*\(\d{4}\):',
            r'^[A-Z][a-z]+,\s+[A-Z][a-z]+\.\s*[A-Z][a-z]+.*?\.\s*[A-Z][a-z]+:\s*[A-Z][a-z]+,\s*\d{4}',
            r'^\d+\.\s*[A-Z][a-z]+,\s*[A-Z][a-z]+.*?\s*\([A-Z][a-z]+:\s*[A-Z][a-z]+,\s*\d{4}\)'
        ],
        year_pattern=r'\(\d{4}\)|\,\s*\d{4}(?:\.|,)',
        author_pattern=r'^(?:\d+\.\s*)?[A-Z][a-z]+,\s+[A-Z][a-z]+',
        title_indicators=['Quotes for articles', 'Italics for books', 'Footnote numbers'],
        common_punctuation={'after_author': '.', 'after_title': '.', 'publisher_separator': ':'}
    ),
    
    'IEEE': CitationStyle(
        name='IEEE',
        patterns=[
            r'^\[\d+\]\s*[A-Z]\.\s*[A-Z][a-z]+(?:\s+and\s+[A-Z]\.\s*[A-Z][a-z]+)*,\s*"[^"]+,"',
            r'^\[\d+\]\s*[A-Z]\.\s*[A-Z][a-z]+,\s*[A-Z][a-z]+.*?\.\s*[A-Z][a-z]+:\s*[A-Z][a-z]+,\s*\d{4}',
            r'^\[\d+\]\s*[A-Z]\.\s*[A-Z][a-z]+.*?,\s*"[^"]+,"\s*in\s+Proc\.'
        ],
        year_pattern=r',\s*\d{4}(?:\.|,)',
        author_pattern=r'^\[\d+\]\s*[A-Z]\.\s*[A-Z][a-z]+',
        title_indicators=['Quotes for all titles', 'Numbered references', 'Abbreviated first names'],
        common_punctuation={'after_number': ' ', 'after_authors': ',', 'title_quotes': '"'}
    ),
    
    'ACM': CitationStyle(
        name='ACM',
        patterns=[
            r'^\[\d+\]\s*[A-Z][a-z]+\s+(?:[A-Z]\.\s+)?[A-Z][a-z]+(?:\s+and\s+[A-Z][a-z]+\s+(?:[A-Z]\.\s+)?[A-Z][a-z]+)*\.\s+\d{4}\.',
            r'^(?:\[\d+\]\s*)?[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+and\s+[A-Z][a-z]+\s+[A-Z][a-z]+)*\.\s+\d{4}\.',
            r'^(?:\[\d+\]\s*)?[A-Z][a-z]+\s+[A-Z][a-z]+,?\s+et\s+al\.\s+\d{4}\.',
            r'[A-Z][a-z]+\.?\s+[A-Z]+\s+\d+,\s*\d+\s*\([A-Z][a-z]+\.?\s+\d{4}\),\s*\d+[-–]\d+',
            r'In\s+Proceedings\s+of\s+(?:the\s+)?\d*(?:st|nd|rd|th)?\.?\s*[A-Z]',
            r'Article\s+\d+\s*\([A-Z][a-z]+\s+\d{4}\),\s*\d+\s+pages?'
        ],
        year_pattern=r'\b\d{4}\b(?:\.|,|\s|$)',
        author_pattern=r'^(?:\[\d+\]\s*)?[A-Z][a-z]+\s+(?:[A-Z]\.\s+)?[A-Z][a-z]+',
        title_indicators=['Full names preferred', 'Year follows authors with period', 'Square brackets for numbers', 'DOI/URL at end', 'Month in parentheses for journals'],
        common_punctuation={'after_year': '.', 'between_authors': ' and ', 'after_title': '.', 'ref_brackets': '[]', 'page_separator': ', '}
    )
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_domain(url):
    """Extract domain from URL."""
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except:
        return None

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

# ============================================================================
# TEXT PROCESSING AND EXTRACTION FUNCTIONS
# ============================================================================

def split_body_and_references(text):
    """
    Enhanced function to split the extracted PDF text into body_text and references_text.
    Handles various scenarios:
    - Reference headers with page numbers: "Page 15 References"
    - Section numbers: "7. References" or "Section 7 References"
    - Headers anywhere in line: "15 REFERENCES AND BIBLIOGRAPHY"
    - References without explicit headers (detected by reference patterns)
    - Multiple possible reference section locations
    """
    # Handle None or empty text
    if text is None:
        return "", ""
    
    ref_headers = [
        "references", "bibliography", "works cited", "literature cited", 
        "cited works", "sources", "reference list", "citations"
    ]
    
    lines = text.split('\n')
    page_delim_pattern = re.compile(r'^--- Page \d+ ---$', re.IGNORECASE)
    
    def contains_reference_header(line_text):
        """Check if line contains a reference header, handling various prefixes."""
        line_lower = line_text.lower().strip()
        
        # First, check if line starts with a reference header pattern
        # We'll be more lenient with length if it starts with a clear header
        header_at_start = False
        
        # Quick check for headers at start of line
        for header in ref_headers:
            if line_lower.startswith(header) or re.match(rf'^\d+\s*{header}', line_lower) or re.match(rf'^page\s*\d*\s*{header}', line_lower):
                header_at_start = True
                break
        
        # If header is NOT at start and line is too long, skip (likely body text)
        if not header_at_start and len(line_lower) > 100:
            return False
        
        # Skip if line contains common sentence indicators (unless header is clearly at start)
        sentence_indicators = ['the ', 'this ', 'these ', 'those ', 'for ', 'see ', 'in ', 'of ', 'to ', 'with ', 'from ', 'and ', 'or ', 'but ', 'however ', 'therefore ', 'according ', 'based on']
        if not header_at_start and any(indicator in line_lower for indicator in sentence_indicators):
            return False
        
        # Patterns to match reference headers with various prefixes (more restrictive)
        patterns = [
            # Direct header match (start of line or after number/section)
            rf'^({"|".join(ref_headers)})(?:\s|$)',
            # With page numbers: "Page 15 References"
            rf'^page\s+\d+\s+({"|".join(ref_headers)})(?:\s|$)',
            # With section numbers: "7. References" or "Section 7 References"  
            rf'^(?:section\s+)?\d+\.?\s+({"|".join(ref_headers)})(?:\s|$)',
            # Roman numerals: "VII. References"
            rf'^(?:section\s+)?[ivxlcdm]+\.?\s+({"|".join(ref_headers)})(?:\s|$)',
            # Appendix: "Appendix A: References"
            rf'^appendix\s+[a-z]\.?\s*:?\s*({"|".join(ref_headers)})(?:\s|$)',
            # Just numbers before: "15 REFERENCES" (but only if short line)
            rf'^\d+\s+({"|".join(ref_headers)})(?:\s|$)',
            # Concatenated formats: "19REFERENCES", "15BIBLIOGRAPHY" (numbers directly attached)
            rf'^\d+({"|".join(ref_headers)})(?:\s|$)',
            # Concatenated with page: "PageREFERENCES", "Page15REFERENCES"
            rf'^page\d*({"|".join(ref_headers)})(?:\s|$)',
            # Centered or standalone headers (short lines with only the header word)
            rf'^({"|".join(ref_headers)})(?:\s+(?:and\s+)?(?:bibliography|citations|list|sources))?$',
            # Combined headers like "References and Bibliography"
            rf'^({"|".join(ref_headers)})\s+and\s+({"|".join(ref_headers)})$'
        ]
        
        for pattern in patterns:
            if re.search(pattern, line_lower):
                return True
        return False
    
    def extract_content_after_header(line_text, header_found):
        """Extract any content that comes after the reference header in the same line."""
        line_lower = line_text.lower()
        
        # Find where the header ends and extract remainder
        for header in ref_headers:
            if header in line_lower:
                header_pos = line_lower.find(header)
                header_end = header_pos + len(header)
                remainder = line_text[header_end:].strip()
                
                # Remove common separators
                remainder = re.sub(r'^[\s\-.:]+', '', remainder)
                return remainder
        return ""
    
    def looks_like_references_section(lines_sample):
        """Check if a section looks like references based on content patterns."""
        if not lines_sample:
            return False
            
        # Join sample lines to analyze
        sample_text = '\n'.join(lines_sample[:10])  # Check first 10 lines
        
        # Count reference-like patterns
        ref_patterns = [
            r'^\s*\[\d+\]',  # [1] format
            r'^\s*\d+\.',    # 1. format  
            r'^\s*\d+\s+[A-Z]', # Plain number format
            r'[A-Z][a-z]+,\s+[A-Z]\..*?\(\d{4}\)', # Author, A. (year)
            r'et\s+al\.',    # et al.
            r'doi:|DOI:',    # DOI references
            r'https?://',    # URLs
            r'\(\d{4}\)',    # Years in parentheses
            r'vol\.\s*\d+|volume\s+\d+', # Volume numbers
            r'pp?\.\s*\d+',  # Page numbers
        ]
        
        pattern_count = 0
        for pattern in ref_patterns:
            matches = re.findall(pattern, sample_text, re.MULTILINE | re.IGNORECASE)
            pattern_count += len(matches)
        
        # If we find multiple reference indicators, likely a references section
        return pattern_count >= 3
    

    # First pass: Look for explicit reference headers
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # Check if this line contains a reference header
        if contains_reference_header(line_stripped):
            # Check if this header appears after a page delimiter (common case)
            is_after_page_break = (i > 0 and page_delim_pattern.match(lines[i - 1].strip()))
            
            # Extract any content after the header
            remainder = extract_content_after_header(line_stripped, True)
            
            # Find the end of this section (next page or end of document)
            next_page_idx = None
            for j in range(i + 1, len(lines)):
                if page_delim_pattern.match(lines[j].strip()):
                    next_page_idx = j
                    break
            
            # Collect references content, handling blank lines after headers
            if next_page_idx is not None:
                # Include content from the same line as header if present
                refs_lines = []
                if remainder:
                    refs_lines.append(remainder)
                
                # Add content after header, but clean up empty lines
                content_lines = lines[i+1:next_page_idx]
                # Keep all lines but clean up leading/trailing empty lines
                while content_lines and not content_lines[0].strip():
                    content_lines.pop(0)  # Remove leading empty lines
                while content_lines and not content_lines[-1].strip():
                    content_lines.pop()   # Remove trailing empty lines
                    
                refs_lines.extend(content_lines)
                references_text = '\n'.join(refs_lines)
                
                # Remove this section from body (include page marker if header is after page break)
                if is_after_page_break:
                    body_before = lines[:i-1]  # Exclude page marker and header
                else:
                    body_before = lines[:i]  # Just exclude header
                body_after = lines[next_page_idx:]
                body_text = '\n'.join(body_before + body_after)
            else:
                # References go to end of document
                refs_lines = []
                if remainder:
                    refs_lines.append(remainder)
                
                # Add content after header, but clean up empty lines
                content_lines = lines[i+1:]
                while content_lines and not content_lines[0].strip():
                    content_lines.pop(0)  # Remove leading empty lines
                while content_lines and not content_lines[-1].strip():
                    content_lines.pop()   # Remove trailing empty lines
                    
                refs_lines.extend(content_lines)
                references_text = '\n'.join(refs_lines)
                
                # Remove this section from body (include page marker if header is after page break)
                if is_after_page_break:
                    body_text = '\n'.join(lines[:i-1])  # Exclude page marker and header
                else:
                    body_text = '\n'.join(lines[:i])  # Just exclude header
            
            return body_text, references_text
    
    # Second pass: Look for reference sections without explicit headers
    # Check each page for reference-like content
    page_starts = []
    for i, line in enumerate(lines):
        if page_delim_pattern.match(line.strip()):
            page_starts.append(i)
    
    # Check pages starting from the end (references usually at end)
    for page_start in reversed(page_starts[-3:]):  # Check last 3 pages
        # Find next page boundary
        next_page_start = None
        for next_start in page_starts:
            if next_start > page_start:
                next_page_start = next_start
                break
        
        if next_page_start:
            page_lines = lines[page_start+1:next_page_start]
        else:
            page_lines = lines[page_start+1:]
        
        # Skip very short pages
        if len(page_lines) < 5:
            continue
            
        # Check if this page looks like references
        if looks_like_references_section(page_lines):
            references_text = '\n'.join(page_lines)
            
            # Remove this page from body
            body_before = lines[:page_start]
            if next_page_start:
                body_after = lines[next_page_start:]
                body_text = '\n'.join(body_before + body_after)
            else:
                body_text = '\n'.join(body_before)
            
            return body_text, references_text
    
    # Third pass: Look for reference patterns in the last portion of the document
    # Sometimes references appear without clear page boundaries
    if len(lines) > 50:  # Only for reasonably long documents
        last_quarter = lines[-len(lines)//4:]  # Last 25% of document
        
        if looks_like_references_section(last_quarter):
            split_point = len(lines) - len(last_quarter)
            body_text = '\n'.join(lines[:split_point])
            references_text = '\n'.join(last_quarter)
            return body_text, references_text
    
    # If no references section found, return original text
    return text, ""

def extract_in_text_citations(body_text):
    """Extract in-text citations from the body text."""
    if body_text is None:
        body_text = ""
    
    numbered = re.findall(r'\[(\d+)\]', body_text)
    author_year = re.findall(r'\(([A-Z][A-Za-z]+, \d{4}(; [A-Z][A-Za-z]+, \d{4})*)\)', body_text)
    return {
        "numbered": numbered,
        "author_year": author_year
    }

def extract_in_text_citation_sentences(body_text):
    """Extract sentences containing in-text citations."""
    if body_text is None:
        body_text = ""
    
    sentence_pattern = re.compile(r'(?<=[.!?])\s+')
    sentences = sentence_pattern.split(body_text)
    
    numbered_pattern = re.compile(r'\[\d+\]')
    author_year_pattern = re.compile(r'\([A-Z][A-Za-z]+, \d{4}(; [A-Z][A-Za-z]+, \d{4})*\)')
    
    citation_sentences = []
    for sent in sentences:
        found = []
        found += numbered_pattern.findall(sent)
        found += author_year_pattern.findall(sent)
        if found:
            citation_sentences.append({
                "sentence": sent.strip(),
                "citations": found
            })
    return citation_sentences

def extract_references_multiline(text):
    """
    Extract references from multiline text with support for multiple formats:
    - [1] Format: [1] Author, A. (2023). Title...
    - 1. Format: 1. Author, A. (2023). Title...
    - Plain number: 1 Author, A. (2023). Title...
    - Author format: Author, A. et al. (2023). Title...
    - Author year: Authorname et al. (2023)
    """
    if text is None:
        return []
    
    lines = text.split('\n')
    references = []
    current_ref = []

    # Enhanced patterns for different reference formats
    ref_start_patterns = [
        # [1] format - bracketed numbers
        re.compile(r'^\s*\[\d+\]'),
        # 1. format - numbered with period
        re.compile(r'^\s*\d+\.'),
        # Plain number format - just number followed by space and capital letter
        re.compile(r'^\s*\d+\s+[A-Z]'),
        # Author format - starts with author name (Last, First or Last, F.)
        re.compile(r'^\s*[A-Z][a-z]+,\s+[A-Z]\.?\s*(?:[A-Z]\.?\s*)?(?:,?\s*(?:and|&)\s+[A-Z][a-z]+,\s+[A-Z]\.?\s*(?:[A-Z]\.?\s*)?)*(?:,?\s*et\s+al\.)?'),
        # Author et al. format - starts with author followed by et al.
        re.compile(r'^\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+et\s+al\.'),
        # Simple author year format
        re.compile(r'^\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+\(\d{4}\)')
    ]

    def is_reference_start(line_text):
        """Check if line starts a new reference using any of the patterns."""
        line_text = line_text.strip()
        if not line_text:
            return False
        
        for pattern in ref_start_patterns:
            if pattern.match(line_text):
                return True
        return False

    def is_continuation_line(line_text):
        """Check if line is a continuation of a reference."""
        line_text = line_text.strip()
        if not line_text:
            return False
        
        # Common indicators of continuation lines
        continuation_indicators = [
            # Starts with lowercase (likely continuation)
            re.compile(r'^\s*[a-z]'),
            # Starts with common journal/publisher words
            re.compile(r'^\s*(?:In|Proceedings|Journal|IEEE|ACM|Springer|Elsevier)', re.IGNORECASE),
            # Starts with volume/page info
            re.compile(r'^\s*(?:vol\.|volume|pp?\.|pages?|doi:|https?://)', re.IGNORECASE),
            # Starts with punctuation (comma, period)
            re.compile(r'^\s*[,.]'),
            # URL or DOI on separate line
            re.compile(r'^\s*(?:https?://|doi:|www\.)', re.IGNORECASE),
            # Continuation of title or publisher info (common patterns)
            re.compile(r'^\s*(?:regelzaken|nederland|Annaouderenzorg)', re.IGNORECASE)
        ]
        
        for pattern in continuation_indicators:
            if pattern.match(line_text):
                return True
        return False
    
    def looks_like_new_reference(line_text, previous_line=None):
        """Enhanced logic to determine if a line starts a new reference."""
        line_text = line_text.strip()
        if not line_text:
            return False
            
        # If it matches standard patterns, it's definitely a new reference
        if is_reference_start(line_text):
            return True
            
        # Additional heuristics for author-style references
        # Check if line starts with author name pattern (e.g., "Alzheimer Nederland.")
        author_patterns = [
            # Organization or author name followed by period and year
            re.compile(r'^[A-Z][a-zA-Z\s]+\.?\s*\([12]\d{3}', re.IGNORECASE),
            # Organization name followed by colon (like "Alzheimer Nederland:")
            re.compile(r'^[A-Z][a-zA-Z\s]+:\s*', re.IGNORECASE),
            # Simple organization or author name at start
            re.compile(r'^[A-Z][a-zA-Z\s]{10,}\.?\s*\(', re.IGNORECASE)
        ]
        
        for pattern in author_patterns:
            if pattern.match(line_text):
                return True
        
        # If previous line ended with URL or period and this starts with capital, likely new ref
        if previous_line and (previous_line.strip().endswith('/') or previous_line.strip().endswith('.')):
            if line_text[0].isupper() and len(line_text) > 10:
                return True
                
        return False

    previous_line = None
    for line in lines:
        line_stripped = line.strip()
        
        # Skip empty lines but track them for reference separation
        if not line_stripped:
            # Empty line might separate references, save current if exists
            if current_ref:
                references.append(' '.join(current_ref).strip())
                current_ref = []
            previous_line = line
            continue
            
        # Check if this line starts a new reference
        if looks_like_new_reference(line_stripped, previous_line) or is_reference_start(line_stripped):
            # Save previous reference if exists
            if current_ref:
                references.append(' '.join(current_ref).strip())
                current_ref = []
            current_ref.append(line_stripped)
        elif current_ref and (is_continuation_line(line_stripped) or 
                             # If we're already in a reference and line doesn't clearly start a new one
                             not looks_like_new_reference(line_stripped, previous_line)):
            current_ref.append(line_stripped)
        else:
            # Line might start a new reference or be standalone
            if current_ref:
                references.append(' '.join(current_ref).strip())
                current_ref = []
            current_ref.append(line_stripped)
        
        previous_line = line
    
    # Add final reference if exists
    if current_ref:
        references.append(' '.join(current_ref).strip())

    # Filter out very short references and common non-reference patterns
    filtered_references = []
    for ref in references:
        ref_lower = ref.lower().strip()
        
        # Skip common non-reference patterns
        skip_patterns = [
            'no references available',
            'no citations found',
            'references not available',
            'none available',
            'not applicable',
            'n/a',
            'tbd',
            'to be determined',
            'coming soon',
            'under construction'
        ]
        
        # Check if this is a non-reference pattern
        is_non_reference = any(pattern in ref_lower for pattern in skip_patterns)
        
        # Only include references with reasonable length, content, and not matching skip patterns
        if not is_non_reference and len(ref) > 20 and (' ' in ref or ',' in ref):
            # Additional check: must contain some reference-like indicators
            ref_indicators = [
                r'\d{4}',  # Year
                r'[A-Z][a-z]+,',  # Author pattern
                r'\..*\.',  # Multiple periods (title/journal pattern)
                r'http',  # URL
                r'doi',  # DOI
                r'vol\.?|volume',  # Volume
                r'pp?\.?',  # Pages
                r'journal|proceedings|conference',  # Publication types
            ]
            
            has_indicator = any(re.search(pattern, ref, re.IGNORECASE) for pattern in ref_indicators)
            if has_indicator:
                filtered_references.append(ref)
    
    return filtered_references

# ============================================================================
# CITATION STYLE ANALYSIS FUNCTIONS
# ============================================================================

def detect_citation_style(reference: str) -> Tuple[str, float]:
    """
    Detect the citation style of a reference.
    Returns tuple of (style_name, confidence_score)
    """
    reference = reference.strip()
    best_match = ('Unknown', 0.0)
    
    for style_name, style in CITATION_STYLES.items():
        score = 0.0
        max_score = len(style.patterns) + 3
        
        for pattern in style.patterns:
            if re.search(pattern, reference, re.IGNORECASE):
                score += 1
                break
        
        if re.search(style.year_pattern, reference):
            score += 1
        
        if re.search(style.author_pattern, reference):
            score += 1
        
        punct_matches = 0
        for key, punct in style.common_punctuation.items():
            if punct in reference:
                punct_matches += 1
        score += punct_matches / len(style.common_punctuation)
        
        confidence = score / max_score
        if confidence > best_match[1]:
            best_match = (style_name, confidence)
    
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
    
    # Basic validations
    if not components['authors']:
        validation['errors'].append("Missing author information")
        validation['is_valid'] = False
    
    if not components['year']:
        validation['errors'].append("Missing publication year")
        validation['is_valid'] = False
    
    if not components['title']:
        validation['errors'].append("Missing title")
        validation['is_valid'] = False
    
    return validation

# ============================================================================
# URL AND DOI VALIDATION FUNCTIONS
# ============================================================================

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

def validate_doi(doi):
    """Validate a DOI by checking if it resolves."""
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

def validate_reference(ref):
    """Validate a reference by checking various sources."""
    results = {
        'valid': False,
        'doi_found': False,
        'doi_valid': False,
        'url_found': False,
        'url_valid': False,
        'scholar_search': None,
        'message': '',
        'rate_limited': False,
        'acm_url': False,
        'doi_text': '',
        'url_text': ''
    }
    
    # Extract DOI from reference and validate it
    doi_match = re.search(r'(?:doi:?\s*|https?://doi\.org/)(10\.\d{4,}/[^\s,]+)', ref, re.IGNORECASE)
    if doi_match:
        doi = doi_match.group(1)
        results['doi_found'] = True
        results['doi_text'] = doi
        
        # Check rate limit for DOI validation
        if check_rate_limit('doi.org'):
            try:
                results['doi_valid'] = validate_doi(doi)
                if results['doi_valid']:
                    results['valid'] = True
                    results['message'] = f"✅ DOI validated successfully: {doi}"
                else:
                    results['message'] = f"❌ DOI does not resolve: {doi}"
            except Exception as e:
                results['message'] = f"⚠️ Error validating DOI {doi}: {str(e)}"
        else:
            results['rate_limited'] = True
            results['message'] = f"⏳ Rate limited - cannot validate DOI: {doi}"
    
    # Extract URL from reference (excluding DOI URLs)
    url_match = re.search(r'https?://(?!doi\.org)[^\s<>"\']+', ref)
    if url_match:
        url = url_match.group(0)
        results['url_found'] = True
        results['url_text'] = clean_url(url)
        
        # For now, we don't validate general URLs due to rate limiting concerns
        # But we mark that a URL was found
        results['message'] += f" | 🔗 URL found: {results['url_text']}" if results['message'] else f"🔗 URL found: {results['url_text']}"
    
    # Create Google Scholar search URL for manual verification
    search_query = urllib.parse.quote(ref[:200])
    results['scholar_search'] = f"https://scholar.google.com/scholar?q={search_query}"
    
    # If no DOI or URL validation occurred, provide default message
    if not results['doi_found'] and not results['url_found']:
        results['message'] = f"ℹ️ No DOI or URL found for validation"
    
    return results

# ============================================================================
# UI DISPLAY FUNCTIONS
# ============================================================================

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

def display_reference_with_style(ref, validation_result, style_info, ref_type="standard"):
    """Display reference with both validation status and citation style analysis."""
    style, confidence = style_info
    
    st.markdown(f"**Reference:** {ref}")
    st.markdown(format_style_confidence(style, confidence), unsafe_allow_html=True)
    
    # Display DOI and URL validation status
    validation_msgs = []
    if validation_result['doi_found']:
        if validation_result['rate_limited']:
            validation_msgs.append(f"⏳ **DOI:** {validation_result['doi_text']} (Rate limited - cannot validate)")
        elif validation_result['doi_valid']:
            validation_msgs.append(f"✅ **DOI:** {validation_result['doi_text']} (Valid)")
        else:
            validation_msgs.append(f"❌ **DOI:** {validation_result['doi_text']} (Invalid or unreachable)")
    
    if validation_result['url_found']:
        validation_msgs.append(f"🔗 **URL:** {validation_result['url_text']} (Found)")
    
    if validation_msgs:
        st.markdown("**Validation Status:**")
        for msg in validation_msgs:
            st.markdown(f"- {msg}")
    
    # Display validation message if present
    if validation_result['message']:
        if validation_result['doi_valid']:
            st.success(validation_result['message'])
        elif validation_result['doi_found'] and not validation_result['doi_valid'] and not validation_result['rate_limited']:
            st.error(validation_result['message'])
        elif validation_result['rate_limited']:
            st.warning(validation_result['message'])
        else:
            st.info(validation_result['message'])
    
    if style != 'Unknown':
        format_validation = validate_citation_format(ref, style)
        
        if format_validation['errors']:
            st.error("**Format Errors:**")
            for error in format_validation['errors']:
                st.markdown(f"- ❌ {error}")
        
        if format_validation['warnings']:
            st.warning("**Format Warnings:**")
            for warning in format_validation['warnings']:
                st.markdown(f"- ⚠️ {warning}")
        
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
                    if components['doi']:
                        doi_status = "✅ Valid" if validation_result.get('doi_valid') else "❓ Not validated"
                        st.markdown(f"**DOI:** {components['doi']} ({doi_status})")
                with cols[1]:
                    if components['source']:
                        st.markdown(f"**Source:** {components['source']}")
                    if components['volume']:
                        st.markdown(f"**Volume:** {components['volume']}")
                    if components['pages']:
                        st.markdown(f"**Pages:** {components['pages']}")
                    if components['url']:
                        st.markdown(f"**URL:** {components['url']}")
    
    if validation_result['scholar_search']:
        st.info(f"[🔍 Verify on Google Scholar]({validation_result['scholar_search']})")

def create_citation_report(references, style_counts):
    """Generate a comprehensive citation analysis report."""
    report = "# Citation Analysis Report\n\n"
    report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += f"Total References: {len(references)}\n\n"
    
    report += "## Citation Style Summary\n"
    for style, count in sorted(style_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(references)) * 100
        report += f"- {style}: {count} ({percentage:.1f}%)\n"
    report += "\n"
    
    report += "## Detailed Reference Analysis\n\n"
    for i, ref in enumerate(references, 1):
        style_info = detect_citation_style(ref)
        validation_result = validate_reference(ref)
        
        report += f"### Reference {i}\n"
        report += f"**Text:** {ref}\n"
        report += f"**Style:** {style_info[0]} (Confidence: {style_info[1]:.1%})\n"
        
        # DOI validation status
        if validation_result['doi_found']:
            if validation_result['rate_limited']:
                report += f"**DOI:** {validation_result['doi_text']} (Rate limited)\n"
            elif validation_result['doi_valid']:
                report += f"**DOI:** {validation_result['doi_text']} (Valid)\n"
            else:
                report += f"**DOI:** {validation_result['doi_text']} (Invalid)\n"
        
        # URL status
        if validation_result['url_found']:
            report += f"**URL:** {validation_result['url_text']} (Found)\n"
        
        report += f"**Overall Valid:** {'Yes' if validation_result['valid'] else 'No'}\n"
        
        if style_info[0] != 'Unknown':
            format_validation = validate_citation_format(ref, style_info[0])
            report += f"**Format Valid:** {'Yes' if format_validation['is_valid'] else 'No'}\n"
            if format_validation['errors']:
                report += f"**Errors:** {', '.join(format_validation['errors'])}\n"
        
        report += "\n"
    
    return report

# ============================================================================
# INTERACTIVE RE-ANALYSIS FUNCTIONS
# ============================================================================

def perform_reanalysis(modified_content):
    """Perform re-analysis on modified content."""
    # Handle None or empty content
    if modified_content is None:
        modified_content = ""
    
    # Split body and references
    body_text, references_text = split_body_and_references(modified_content)
    references = extract_references_multiline(references_text)
    in_text_citations = extract_in_text_citations(body_text)
    citation_sentences = extract_in_text_citation_sentences(body_text)
    
    # Style analysis
    style_counts = defaultdict(int)
    for ref in references:
        style_info = detect_citation_style(ref)
        style_counts[style_info[0]] += 1
    
    return {
        'body_text': body_text,
        'references_text': references_text,
        'references': references,
        'in_text_citations': in_text_citations,
        'citation_sentences': citation_sentences,
        'style_counts': style_counts
    }

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application function."""
    
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

    # Main title
    st.title("📄 PDF Citation Analyzer")
    
    # Description
    st.markdown("""
        Upload your PDF file and extract its content. The tool will:
        - Extract text from all pages
        - Detect and validate references with citation style analysis
        - Check if citations follow academic formats (APA, MLA, Chicago, IEEE, ACM)
        - Analyze in-text citations and reference consistency
        
        **🆕 Interactive Feature:** After extraction, you can edit the content and click **"Re-analyze Citations"** to handle custom reference formats or fix extraction issues.
    """)

    # Create layout
    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### Upload PDF")
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

    with col2:
        if uploaded_file is not None:
            try:
                # Reset session state when a new file is uploaded
                if 'uploaded_file_name' not in st.session_state or st.session_state.uploaded_file_name != uploaded_file.name:
                    st.session_state.uploaded_file_name = uploaded_file.name
                    st.session_state.current_content = None
                    st.session_state.analysis_results = None
                
                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                
                text_content = ""
                with st.spinner("Extracting text from PDF..."):
                    for page_num, page in enumerate(pdf_reader.pages, 1):
                        try:
                            # Add page marker
                            text_content += f"\n--- Page {page_num} ---\n"
                            
                            # Extract text with error handling
                            try:
                                page_text = page.extract_text()
                            except UnicodeEncodeError as e:
                                # Handle encoding errors by using a different encoding
                                page_text = page.extract_text().encode('utf-8', errors='replace').decode('utf-8')
                            except Exception as e:
                                st.warning(f"Warning: Error extracting text from page {page_num}: {str(e)}")
                                page_text = f"[Error extracting text from page {page_num}]"
                            
                            # Clean the text to remove invalid characters
                            page_text = ''.join(char for char in page_text if ord(char) < 0x10000)
                            text_content += page_text
                            
                        except Exception as e:
                            st.warning(f"Warning: Error processing page {page_num}: {str(e)}")
                            text_content += f"\n[Error processing page {page_num}]\n"
                
                if not text_content.strip():
                    st.error("No text could be extracted from the PDF. The file might be scanned or contain only images.")
                    return
                
                st.success(f"Successfully extracted text from {len(pdf_reader.pages)} pages!")
                
                # Create tabs
                tab1, tab2, tab3, tab4 = st.tabs(["📝 Content", "🔎 In-Text Citations", "📚 References", "📊 Citation Analysis"])
                
                # Initialize session state for content and analysis results
                if 'current_content' not in st.session_state or st.session_state.current_content is None:
                    st.session_state.current_content = text_content
                if 'analysis_results' not in st.session_state:
                    st.session_state.analysis_results = None
                
                # Ensure current_content is not None before analysis
                if st.session_state.current_content is None:
                    st.session_state.current_content = text_content
                
                # Perform initial analysis or use cached results
                if st.session_state.analysis_results is None:
                    try:
                        st.session_state.analysis_results = perform_reanalysis(st.session_state.current_content)
                    except Exception as e:
                        st.error(f"Error during initial analysis: {str(e)}")
                        # Create empty results as fallback
                        st.session_state.analysis_results = {
                            'body_text': st.session_state.current_content or "",
                            'references_text': "",
                            'references': [],
                            'in_text_citations': {'numbered': [], 'author_year': []},
                            'citation_sentences': [],
                            'style_counts': defaultdict(int)
                        }
                
                with tab1:
                    st.subheader("Extracted Content")
                    
                    # Instructions for interactive feature
                    with st.expander("💡 How to use Interactive Re-analysis"):
                        st.markdown("""
                        **Step 1:** Review the extracted content below
                        
                        **Step 2:** Edit the content if needed:
                        - Fix OCR errors or formatting issues
                        - Manually separate references section if not detected
                        - Add missing reference headers (e.g., "References", "Bibliography")
                        - Fix malformed reference entries
                        
                        **Step 3:** Click **"Re-analyze Citations"** to update all analysis tabs
                        
                        **Common fixes:**
                        - Add `--- Page X ---` markers to separate sections
                        - Add `References` header before reference list
                        - Fix concatenated headers like `19REFERENCES` → `19 REFERENCES`
                        - Separate merged references into individual lines
                        """)
                    
                    # Editable text area for content modification
                    content_value = st.session_state.current_content if st.session_state.current_content is not None else ""
                    
                    # Use a dynamic key to force refresh when needed
                    if 'text_area_key' not in st.session_state:
                        st.session_state.text_area_key = 0
                    
                    modified_content = st.text_area(
                        "PDF Content (You can edit this content and re-analyze)",
                        value=content_value,
                        height=400,
                        key=f"content_editor_{st.session_state.text_area_key}",
                        help="Edit the extracted content to fix issues, then click 'Re-analyze Citations'"
                    )
                    
                    # Debug info
                    if modified_content != content_value:
                        st.info(f"🔄 Content changed! Modified length: {len(modified_content)}, Original length: {len(content_value)}")
                        st.info("Click 'Re-analyze Citations' to update the analysis.")
                    
                    # Additional debug information
                    st.caption(f"🔍 Debug: Text area content length: {len(modified_content)} | Session content length: {len(st.session_state.current_content) if st.session_state.current_content else 0}")
                    
                    # Re-analyze button
                    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
                    
                    with col_btn1:
                        if st.button("🔄 Re-analyze Citations", type="primary"):
                            # Always use the current content from the text area, not session state comparison
                            st.session_state.current_content = modified_content
                            try:
                                with st.spinner("Re-analyzing citations..."):
                                    new_results = perform_reanalysis(modified_content)
                                    st.session_state.analysis_results = new_results
                                
                                st.success("✅ Re-analysis completed!")
                                st.info(f"Found {len(new_results['references'])} references, {len(new_results['citation_sentences'])} citation sentences")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error during re-analysis: {str(e)}")
                    
                    with col_btn2:
                        if st.button("↩️ Reset to Original"):
                            st.session_state.current_content = text_content
                            st.session_state.text_area_key += 1  # Force text area refresh
                            try:
                                st.session_state.analysis_results = perform_reanalysis(text_content)
                                st.success("✅ Reset to original content!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error during reset: {str(e)}")
                    
                    with col_btn3:
                        if st.button("🔄 Force Refresh"):
                            st.session_state.text_area_key += 1  # Force text area refresh
                            st.success("✅ Text area refreshed!")
                            st.rerun()
                    
                    # Download button and statistics
                    if st.session_state.current_content:
                        st.download_button(
                            label="Download Current Text",
                            data=st.session_state.current_content,
                            file_name=f"{Path(uploaded_file.name).stem}_extracted.txt",
                            mime="text/plain"
                        )
                        
                        # Show statistics
                        original_length = len(text_content) if text_content else 0
                        current_content = st.session_state.current_content or ""
                        current_length = len(current_content)
                        length_diff = current_length - original_length
                        
                        st.info(f"""
                            📊 **Content Statistics**
                            - File name: {uploaded_file.name}
                            - Number of pages: {len(pdf_reader.pages)}
                            - Original text length: {original_length:,} characters
                            - Current text length: {current_length:,} characters
                            - Difference: {length_diff:+,} characters
                        """)
                
                # Get current analysis results
                results = st.session_state.analysis_results
                
                with tab2:
                    st.subheader("In-Text Citations (with Sentences)")
                    citation_sentences = results['citation_sentences']
                    
                    # Debug info
                    current_content_length = len(st.session_state.current_content) if st.session_state.current_content else 0
                    st.caption(f"🔍 Debug: Content length: {current_content_length} chars | Analysis timestamp: {id(results)}")
                    
                    if citation_sentences:
                        st.info(f"Found {len(citation_sentences)} sentences with citations")
                        for item in citation_sentences:
                            st.markdown(f"**Citations:** {', '.join(item['citations'])}")
                            st.write(item["sentence"])
                            st.markdown("---")
                    else:
                        st.info("No in-text citations found in the document.")
                
                with tab3:
                    st.subheader("References Section")
                    references_text = results['references_text']
                    references = results['references']
                    
                    # Enhanced debug info
                    current_content_length = len(st.session_state.current_content) if st.session_state.current_content else 0
                    st.caption(f"🔍 Debug: Content length: {current_content_length} chars | References text: {len(references_text)} chars | Found {len(references)} references | Analysis ID: {id(results)} | Text area key: {st.session_state.get('text_area_key', 'N/A')}")
                    
                    # Show first 200 chars of current content for verification
                    if st.session_state.current_content:
                        st.caption(f"📄 Current content preview: {repr(st.session_state.current_content[:200])}...")
                    
                    with st.expander("🔍 Raw References Text"):
                        st.text(references_text)
                    
                    st.write("**Extracted References:**")
                    if references:
                        st.write(f"Found {len(references)} references:")
                        for i, ref in enumerate(references, 1):
                            st.markdown(f"**[{i}]** {ref}")
                    else:
                        st.info("No references found in the document.")
                
                with tab4:
                    st.subheader("Citation Analysis")
                    references = results['references']
                    style_counts = results['style_counts']
                    
                    if references:
                        for i, ref in enumerate(references, 1):
                            st.markdown(f"### Reference {i}")
                            style_info = detect_citation_style(ref)
                            validation_result = validate_reference(ref)
                            display_reference_with_style(ref, validation_result, style_info)
                            st.markdown("---")
                        
                        with st.expander("📊 Citation Style Summary"):
                            st.markdown("### Detected Citation Styles")
                            for style, count in sorted(style_counts.items(), key=lambda x: x[1], reverse=True):
                                percentage = (count / len(references)) * 100
                                st.markdown(f"- **{style}**: {count} references ({percentage:.1f}%)")
                            if len(style_counts) > 1 and style_counts['Unknown'] < len(references) * 0.5:
                                st.warning("⚠️ Multiple citation styles detected. Consider using a consistent style throughout the document.")
                        
                        # Generate and offer download report
                        citation_report = create_citation_report(references, style_counts)
                        st.download_button(
                            label="Download Citation Analysis Report",
                            data=citation_report,
                            file_name=f"{Path(uploaded_file.name).stem}_citation_analysis.txt",
                            mime="text/plain"
                        )
                    else:
                        st.info("No references found for analysis.")
                
            except Exception as e:
                st.error(f"Error processing PDF: {str(e)}")
                st.warning("Please make sure you've uploaded a valid PDF file.")
        else:
            st.markdown("""
                ### Preview Area
                Upload a PDF file to see:
                - Extracted content with page numbers
                - In-text citations with context sentences
                - References with citation style detection
                - Comprehensive citation analysis
                - Downloadable analysis report
            """)

    # Footer
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: #666;'>
            Made with ❤️ using Streamlit, PyPDF2, and Citation Style Analysis
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()