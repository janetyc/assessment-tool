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
    Split the extracted PDF text into body_text and references_text.
    Only when a page's first line begins with a reference header
    (e.g. "References"), remove that header and collect the rest of that page
    as the references section, stopping at the next page break.
    """
    ref_headers = [
        "references", "bibliography", "works cited", "literature cited", 
        "cited works", "sources"
    ]
    
    lines = text.split('\n')
    page_delim_pattern = re.compile(r'^--- Page \d+ ---$', re.IGNORECASE)
    
    for i, line in enumerate(lines):
        if i > 0 and page_delim_pattern.match(lines[i - 1].strip()):
            first_line = line.strip()
            lower = first_line.lower()
            
            for header in ref_headers:
                if header in lower:
                    remainder = first_line[len(header):].lstrip()
                    
                    next_page_idx = None
                    for j in range(i + 1, len(lines)):
                        if page_delim_pattern.match(lines[j].strip()):
                            next_page_idx = j
                            break
                    
                    if next_page_idx is not None:
                        if remainder:
                            refs_lines = [remainder] + lines[i+1:next_page_idx]
                        else:
                            refs_lines = lines[i+1:next_page_idx]
                        references_text = '\n'.join(refs_lines)
                        
                        body_before = lines[:i]
                        body_after = lines[next_page_idx:]
                        body_text = '\n'.join(body_before + body_after)
                    else:
                        if remainder:
                            refs_lines = [remainder] + lines[i+1:]
                        else:
                            refs_lines = lines[i+1:]
                        references_text = '\n'.join(refs_lines)
                        body_text = '\n'.join(lines[:i])
                    
                    return body_text, references_text
    
    return text, ""

def extract_in_text_citations(body_text):
    """Extract in-text citations from the body text."""
    numbered = re.findall(r'\[(\d+)\]', body_text)
    author_year = re.findall(r'\(([A-Z][A-Za-z]+, \d{4}(; [A-Z][A-Za-z]+, \d{4})*)\)', body_text)
    return {
        "numbered": numbered,
        "author_year": author_year
    }

def extract_in_text_citation_sentences(body_text):
    """Extract sentences containing in-text citations."""
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
    """Extract references from multiline text."""
    lines = text.split('\n')
    references = []
    current_ref = []

    ref_start_pattern = re.compile(r'^\s*(\[\d+\]|\d+\.)')

    for line in lines:
        if ref_start_pattern.match(line.strip()):
            if current_ref:
                references.append(' '.join(current_ref).strip())
                current_ref = []
            current_ref.append(line.strip())
        else:
            if current_ref:
                current_ref.append(line.strip())
    
    if current_ref:
        references.append(' '.join(current_ref).strip())

    return references

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
        'url_found': False,
        'scholar_search': None,
        'message': '',
        'rate_limited': False,
        'acm_url': False
    }
    
    # Create Google Scholar search URL for manual verification
    search_query = urllib.parse.quote(ref[:200])
    results['scholar_search'] = f"https://scholar.google.com/scholar?q={search_query}"
    
    if not results['valid']:
        results['message'] = f"ℹ️ Reference needs manual verification: {ref}"
    
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
                with cols[1]:
                    if components['source']:
                        st.markdown(f"**Source:** {components['source']}")
                    if components['volume']:
                        st.markdown(f"**Volume:** {components['volume']}")
                    if components['pages']:
                        st.markdown(f"**Pages:** {components['pages']}")
    
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
        report += f"**URL/DOI Valid:** {'Yes' if validation_result['valid'] else 'No'}\n"
        
        if style_info[0] != 'Unknown':
            format_validation = validate_citation_format(ref, style_info[0])
            report += f"**Format Valid:** {'Yes' if format_validation['is_valid'] else 'No'}\n"
            if format_validation['errors']:
                report += f"**Errors:** {', '.join(format_validation['errors'])}\n"
        
        report += "\n"
    
    return report

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
    """)

    # Create layout
    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### Upload PDF")
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

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
                
                # Create tabs
                tab1, tab2, tab3, tab4 = st.tabs(["📝 Content", "🔎 In-Text Citations", "📚 References", "📊 Citation Analysis"])
                
                # Split body and references
                body_text, references_text = split_body_and_references(text_content)
                references = extract_references_multiline(references_text)
                in_text_citations = extract_in_text_citations(body_text)
                
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
                    st.subheader("In-Text Citations (with Sentences)")
                    citation_sentences = extract_in_text_citation_sentences(body_text)
                    if citation_sentences:
                        for item in citation_sentences:
                            st.markdown(f"**Citations:** {', '.join(item['citations'])}")
                            st.write(item["sentence"])
                            st.markdown("---")
                    else:
                        st.info("No in-text citations found in the document.")
                
                with tab3:
                    st.subheader("References Section")
                    st.write(references_text)
                    st.write("--------------------------------")

                    if references:
                        st.write(f"Found {len(references)} references:")
                        for i, ref in enumerate(references, 1):
                            st.markdown(f"**[{i}]** {ref}")
                    else:
                        st.info("No references found in the document.")
                
                with tab4:
                    st.subheader("Citation Analysis")
                    if references:
                        style_counts = defaultdict(int)
                        for i, ref in enumerate(references, 1):
                            st.markdown(f"### Reference {i}")
                            style_info = detect_citation_style(ref)
                            style_counts[style_info[0]] += 1
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