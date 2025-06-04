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
    </style>
""", unsafe_allow_html=True)

# Main title with emoji
st.title("📄 PDF Content Extractor")

# Add description
st.markdown("""
    Upload your PDF file and extract its content. The tool will:
    - Extract text from all pages
    - Show the content in a readable format
    - Allow you to download the extracted text
""")

# Create two columns
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### Upload PDF")
    # File uploader widget with error handling
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

with col2:
    if uploaded_file is not None:
        try:
            # Read PDF content
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            
            # Extract text from all pages
            text_content = ""
            with st.spinner("Extracting text from PDF..."):
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text_content += f"\n--- Page {page_num} ---\n"
                    text_content += page.extract_text()
            
            # Success message
            st.success(f"Successfully extracted text from {len(pdf_reader.pages)} pages!")
            
            # Create tabs for different views
            tab1, tab2 = st.tabs(["📝 Content", "📚 References"])
            
            with tab1:
                # Display the extracted text
                st.subheader("Extracted Content")
                st.text_area("PDF Content", text_content, height=400)
                
                # Download button for extracted text
                if text_content:
                    # Create download button
                    st.download_button(
                        label="Download Extracted Text",
                        data=text_content,
                        file_name=f"{Path(uploaded_file.name).stem}_extracted.txt",
                        mime="text/plain"
                    )
                    
                    # Show file statistics
                    st.info(f"""
                        📊 **File Statistics**
                        - File name: {uploaded_file.name}
                        - Number of pages: {len(pdf_reader.pages)}
                        - Extracted text length: {len(text_content)} characters
                    """)
            
            with tab2:
                st.subheader("References")
                
                def extract_doi_from_url(url):
                    """Extract DOI from a URL if present."""
                    # First, clean any spaces or unwanted characters
                    url = re.sub(r'\s+', '', url)
                    
                    doi_patterns = [
                        r'10\.\d{4,}/[-._;()/:\w]+',  # Standard DOI pattern
                        r'doi\.org/10\.\d{4,}/[-._;()/:\w]+',  # DOI.org URL pattern
                        r'dx\.doi\.org/10\.\d{4,}/[-._;()/:\w]+',  # dx.doi.org URL pattern
                        r'doi/(?:abs|pdf|full|book|citation)?/?10\.\d{4,}/[-._;()/:\w]+',  # DOI in path
                    ]
                    
                    for pattern in doi_patterns:
                        match = re.search(pattern, url, re.IGNORECASE)
                        if match:
                            doi = match.group(0)
                            # If the pattern matched includes 'doi.org' or similar, extract just the DOI part
                            if '/' in doi and '10.' in doi:
                                doi = doi[doi.index('10.'):]
                            return doi.strip()
                    return None

                def extract_urls_from_text(text):
                    """Extract potential URLs from text, handling broken or spaced URLs."""
                    # More comprehensive URL pattern that can handle spaces
                    url_pattern = r'(?:https?://|www\.)[^\s<>"\']+(?:\s+[^\s<>"\']+)*'
                    
                    potential_urls = []
                    for match in re.finditer(url_pattern, text, re.IGNORECASE):
                        # Get the full match and any trailing text that might be part of the URL
                        url = match.group(0)
                        # Clean up the URL
                        cleaned_url = clean_url(url)
                        if cleaned_url:
                            potential_urls.append(cleaned_url)
                    return potential_urls

                def clean_url(url):
                    """Clean and encode URL properly, handling spaces and special characters."""
                    if not url:
                        return None

                    try:
                        # Initial cleanup
                        url = url.strip()
                        
                        # Handle cases where the URL is split across spaces
                        url_parts = url.split()
                        if len(url_parts) > 1:
                            # Join parts that look like they belong to the URL
                            cleaned_parts = []
                            for part in url_parts:
                                # Remove unwanted characters from each part
                                part = re.sub(r'["\'\[\]<>{}]', '', part)
                                part = part.strip('.,;:()[]{}')
                                if part:
                                    cleaned_parts.append(part)
                            url = ''.join(cleaned_parts)
                        
                        # Remove any remaining whitespace
                        url = re.sub(r'\s+', '', url)
                        
                        # Fix backslashes
                        url = url.replace('\\', '/')
                        
                        # Handle DOI URLs specially
                        if 'doi' in url.lower():
                            doi = extract_doi_from_url(url)
                            if doi:
                                clean_doi = doi.strip().replace(' ', '')
                                if 'dl.acm.org' in url.lower():
                                    return f"https://dl.acm.org/doi/{clean_doi}"
                                return f"https://doi.org/{clean_doi}"
                        
                        # Remove common unwanted suffixes
                        url = re.sub(r'[.,;:)\]}]+$', '', url)
                        
                        # Ensure URL has proper scheme
                        if not url.lower().startswith(('http://', 'https://')):
                            if url.lower().startswith('www.'):
                                url = 'https://' + url
                            else:
                                return None
                        
                        # Parse and clean URL components
                        parsed = urllib.parse.urlparse(url)
                        
                        # Clean and encode path
                        path_parts = parsed.path.split('/')
                        cleaned_path_parts = []
                        for part in path_parts:
                            # Remove unwanted characters but preserve necessary punctuation
                            part = re.sub(r'["\'\[\]<>{}]', '', part)
                            if part:
                                cleaned_path_parts.append(urllib.parse.quote(part))
                        clean_path = '/'.join(cleaned_path_parts)
                        
                        # Clean and encode query parameters
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
                        
                        # Clean and encode fragment
                        clean_fragment = urllib.parse.quote(parsed.fragment)
                        
                        # Reconstruct the URL
                        cleaned = parsed._replace(
                            path=clean_path,
                            query=clean_query,
                            fragment=clean_fragment
                        )
                        
                        final_url = urllib.parse.urlunparse(cleaned)
                        
                        # Validate final URL format
                        if not re.match(r'https?://.+\..+', final_url):
                            return None
                        
                        return final_url
                    except Exception as e:
                        print(f"Error cleaning URL: {str(e)}")
                        return None

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
                    
                    # Extract and validate URLs
                    urls = extract_urls_from_text(ref)
                    for url in urls:
                        if url:  # Only process if we got a valid URL back
                            results['url_found'] = True
                            
                            # Special handling for ACM URLs
                            if 'dl.acm.org' in url:
                                results['acm_url'] = True
                                if is_valid_acm_url_format(url):
                                    results['valid'] = True
                                    results['message'] = f"✅ Valid ACM Digital Library URL: {url}"
                                    return results
                            
                            # For non-ACM URLs, proceed with normal validation
                            validation_result = validate_url_with_fallback(url)
                            if validation_result is None:
                                results['rate_limited'] = True
                                results['message'] = f"⚠️ Rate limit reached, skipped validation for: {url}"
                            elif validation_result:
                                results['valid'] = True
                                results['message'] = f"✅ Valid URL found: {url}"
                                return results
                    
                    # Check for DOI if URL validation failed
                    if not results['valid']:
                        doi_match = re.search(r'(?i)doi:?\s*(10\.\d{4,}/[^\s,]+)', ref)
                        if doi_match:
                            doi = doi_match.group(1)
                            results['doi_found'] = True
                            if validate_doi(doi):
                                results['valid'] = True
                                results['message'] = f"✅ Valid DOI found: {doi}"
                                return results
                    
                    # Create Google Scholar search URL for manual verification
                    search_query = urllib.parse.quote(ref[:200])
                    results['scholar_search'] = f"https://scholar.google.com/scholar?q={search_query}"
                    
                    if not results['valid']:
                        results['message'] = f"ℹ️ Reference needs manual verification: {ref}"
                    
                    return results

                def extract_references(text):
                    """Extract references from text content."""
                    found_refs = []
                    
                    # Split text into lines and look for a references section
                    lines = text.split('\n')
                    references_section = False
                    references_text = ""
                    start_idx = 0
                    
                    # Common section headers that indicate references
                    ref_headers = ['references', 'bibliography', 'works cited', 'literature cited']
                    
                    # Try to find the references section
                    for i, line in enumerate(lines):
                        if any(header in line.lower() for header in ref_headers):
                            references_section = True
                            start_idx = i
                            references_text = '\n'.join(lines[i:])
                            break
                    
                    if not references_section:
                        return []  # No references section found
                    
                    # Process lines after the references section
                    current_ref = []
                    in_reference = False
                    
                    for line in lines[start_idx + 1:]:
                        line = line.strip()
                        if not line:  # Skip empty lines
                            continue
                            
                        # Check for new reference markers
                        is_new_ref = bool(re.match(r'^\[\d+\]|^\d+\.|^\([0-9]+\)|^[A-Z][a-zA-Z\-]+,?\s+(?:et\s+al\.?\s+)?\(\d{4}\)|^[A-Z][a-zA-Z\-]+,\s*[A-Z]\.|^doi:', line))
                        
                        if is_new_ref:
                            # Save previous reference if exists
                            if current_ref:
                                complete_ref = ' '.join(current_ref)
                                if len(complete_ref) > 20:  # Filter out short matches
                                    found_refs.append(complete_ref)
                            current_ref = [line]
                            in_reference = True
                        elif in_reference:
                            # Continue previous reference
                            # Check if line might be a continuation (starts with lowercase or number)
                            if re.match(r'^[a-z0-9]|^\s*[A-Z]', line):
                                current_ref.append(line)
                            else:
                                # If line starts with something else, assume it's a new section
                                in_reference = False
                    
                    # Add the last reference
                    if current_ref:
                        complete_ref = ' '.join(current_ref)
                        if len(complete_ref) > 20:
                            found_refs.append(complete_ref)
                    
                    return found_refs

                def display_reference_status(ref, validation_result, ref_type="standard"):
                    """Display both reference text and its validation status with alternative verification."""
                    if validation_result['rate_limited']:
                        st.warning(f"{ref}\n\n⚠️ {validation_result['message']}")
                        if validation_result['scholar_search']:
                            st.markdown(f"[🔍 Verify on Google Scholar]({validation_result['scholar_search']})")
                    elif validation_result['valid']:
                        st.success(f"{ref}\n\n✅ Valid Reference")
                    else:
                        if ref_type == "url":
                            st.error(f"{ref}\n\n❌ URL not accessible")
                            if validation_result['scholar_search']:
                                st.markdown("""
                                **Alternative Verification Methods:**
                                """)
                                st.markdown(f"1. [🔍 Verify on Google Scholar]({validation_result['scholar_search']})")
                                # Create a web archive search link
                                encoded_url = urllib.parse.quote(ref)
                                wayback_url = f"https://web.archive.org/web/*/{encoded_url}"
                                st.markdown(f"2. [📚 Check Web Archive]({wayback_url})")
                        elif ref_type == "doi":
                            st.error(f"{ref}\n\n❌ Invalid DOI")
                            if validation_result['scholar_search']:
                                st.markdown(f"[🔍 Verify on Google Scholar]({validation_result['scholar_search']})")
                        else:
                            st.info(f"{ref}\n\n[🔍 Verify on Google Scholar]({validation_result['scholar_search']})")

                # Add rate limiting tracking
                RATE_LIMITS = {
                    'dl.acm.org': {'requests': 0, 'last_reset': datetime.now(), 'max_requests': 10, 'reset_interval': 60},
                    'doi.org': {'requests': 0, 'last_reset': datetime.now(), 'max_requests': 30, 'reset_interval': 60},
                    'default': {'requests': 0, 'last_reset': datetime.now(), 'max_requests': 50, 'reset_interval': 60}
                }

                def check_rate_limit(domain):
                    """Check if we've hit rate limit for a domain."""
                    now = datetime.now()
                    rate_info = RATE_LIMITS.get(domain, RATE_LIMITS['default'])
                    
                    # Reset counter if enough time has passed
                    if (now - rate_info['last_reset']).total_seconds() > rate_info['reset_interval']:
                        rate_info['requests'] = 0
                        rate_info['last_reset'] = now
                    
                    # Check if we're over the limit
                    if rate_info['requests'] >= rate_info['max_requests']:
                        return False
                    
                    # Increment counter
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
                    
                    # Remove common prefixes
                    doi = doi.lower().strip()
                    for prefix in ['doi:', 'https://doi.org/', 'http://doi.org/', 'dx.doi.org/']:
                        if doi.startswith(prefix):
                            doi = doi[len(prefix):].strip()
                    
                    # Remove any whitespace and trailing punctuation
                    doi = ''.join(doi.split())  # Remove all whitespace
                    doi = doi.rstrip('.,;')
                    
                    # Extract just the DOI if it's part of a larger string
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
                    
                    # Clean the URL first
                    url = clean_url(url)
                    if not url:
                        return False
                    
                    # Special handling for ACM Digital Library
                    if 'dl.acm.org' in url:
                        # First check if the URL format is valid
                        if is_valid_acm_url_format(url):
                            return True  # Accept valid ACM URL formats without making requests
                        return False
                    
                    # Check if it's a DOI URL
                    doi = extract_doi_from_url(url)
                    if doi:
                        # Validate as DOI instead
                        return validate_doi(doi)
                    
                    domain = get_domain(url)
                    if not domain:
                        return False
                    
                    # Check rate limit for non-ACM domains
                    if not check_rate_limit(domain):
                        print(f"Rate limit reached for {domain}")
                        return None  # None indicates rate limit reached
                    
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

                # Extract references
                references = extract_references(text_content)
                
                if references:
                    st.write(f"Found {len(references)} references:")
                    
                    # Group references by type
                    doi_refs = []
                    url_refs = []
                    other_refs = []
                    
                    for ref in references:
                        if 'doi:' in ref.lower():
                            doi_refs.append(ref)
                        elif 'http' in ref.lower() or 'www.' in ref.lower():
                            url_refs.append(ref)
                        else:
                            other_refs.append(ref)
                    
                    # Display references by type with validation
                    if other_refs:
                        st.markdown("#### Standard References")
                        for i, ref in enumerate(other_refs, 1):
                            st.markdown(f"**Reference {i}:**")
                            validation_result = validate_reference(ref)
                            display_reference_status(ref, validation_result, "standard")
                            st.markdown("---")
                    
                    if doi_refs:
                        st.markdown("#### DOI References")
                        for i, ref in enumerate(doi_refs, 1):
                            st.markdown(f"**Reference {i}:**")
                            validation_result = validate_reference(ref)
                            display_reference_status(ref, validation_result, "doi")
                            st.markdown("---")
                    
                    if url_refs:
                        st.markdown("#### URL References")
                        for i, ref in enumerate(url_refs, 1):
                            st.markdown(f"**Reference {i}:**")
                            validation_result = validate_reference(ref)
                            display_reference_status(ref, validation_result, "url")
                            st.markdown("---")
                    
                    # Add validation summary
                    with st.expander("Validation Summary"):
                        st.markdown("""
                        ### Reference Validation
                        - ✅ Green box: Reference validated (DOI/URL accessible)
                        - ❌ Red box: Reference not validated (DOI/URL not accessible)
                        - ⚠️ Yellow box: Rate limit reached, validation skipped
                        - 🔍 Search link: Manual verification needed
                        
                        **Alternative Verification Methods:**
                        - Google Scholar: Search for the reference in academic literature
                        - Web Archive: Check if the URL was archived in the past
                        
                        Note: Some references may require manual verification through 
                        academic databases or alternative sources.
                        """)
                    
                    # Download references with validation status
                    references_text = "# References\n\n"
                    if other_refs:
                        references_text += "## Standard References\n"
                        for i, ref in enumerate(other_refs, 1):
                            validation_result = validate_reference(ref)
                            status = "✅" if validation_result['valid'] else "❓"
                            references_text += f"{i}. {ref}\nStatus: {status}\n\n"
                    
                    if doi_refs:
                        references_text += "## DOI References\n"
                        for i, ref in enumerate(doi_refs, 1):
                            validation_result = validate_reference(ref)
                            status = "✅" if validation_result['valid'] else "❌"
                            references_text += f"{i}. {ref}\nStatus: {status}\n\n"
                    
                    if url_refs:
                        references_text += "## URL References\n"
                        for i, ref in enumerate(url_refs, 1):
                            validation_result = validate_reference(ref)
                            status = "✅" if validation_result['valid'] else "❌"
                            references_text += f"{i}. {ref}\nStatus: {status}\n\n"
                    
                    st.download_button(
                        label="Download References with Validation Status",
                        data=references_text,
                        file_name=f"{Path(uploaded_file.name).stem}_references_validated.txt",
                        mime="text/plain"
                    )
                else:
                    st.info("No references found in the document. This might happen if:\n" +
                           "- The document doesn't contain references\n" +
                           "- The references are in a format we don't recognize\n" +
                           "- The PDF text extraction wasn't clean")
                
                # Add debug information
                with st.expander("Debug Information"):
                    st.markdown("If references are missing, it might help to see the raw text near the references section.")
                    st.text_area("Raw text (last 2000 characters)", text_content[-2000:], height=200)
                    
                    if references:
                        st.markdown("### Reference Markers Found:")
                        for i, ref in enumerate(references[:5], 1):
                            st.text(f"{i}. {ref[:100]}...")
                
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
            st.warning("Please make sure you've uploaded a valid PDF file.")
    else:
        # Show placeholder when no file is uploaded
        st.markdown("""
            ### Preview Area
            Upload a PDF file to see the extracted content here.
            
            The extracted text will be displayed in a readable format, and you'll be able to:
            - View the content page by page
            - Copy the text directly
            - Download the extracted content as a text file
            - View and download extracted references
        """)

# Add footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: #666;'>
        Made with ❤️ using Streamlit and PyPDF2
    </div>
""", unsafe_allow_html=True)