Assessment Tool
==============================================================================

OVERVIEW
--------
The Assessment Tool includes a PDF Citation Analyzer, which is designed for academic researchers, students, and educators to analyze and validate citations in PDF documents. It provides automated citation style detection, format validation, and comprehensive reporting capabilities.

FEATURES
--------
🔍 Advanced Citation Analysis:
  • Automatic detection of 5 major citation styles (APA, MLA, Chicago, IEEE, ACM)
  • Confidence scoring for style detection accuracy
  • Citation format validation with error reporting
  • Component extraction (authors, titles, years, journals, etc.)

📝 Text Processing:
  • PDF text extraction with page-by-page breakdown
  • Smart separation of body text and references section
  • In-text citation detection (numbered and author-year formats)
  • Context sentence extraction for citations

📊 Quality Assessment:
  • Style consistency analysis across document
  • Format compliance checking
  • Missing component identification
  • Comprehensive validation reporting

🔗 Reference Validation:
  • Google Scholar integration for manual verification
  • Rate-limited external service calls
  • Professional error handling and fallback options

📈 Reporting & Export:
  • Detailed citation analysis reports
  • Style distribution statistics
  • Downloadable analysis results
  • Professional formatting and presentation

SUPPORTED CITATION STYLES
-------------------------
1. APA (American Psychological Association)
   - Author, A. A. (Year). Title. Journal, volume(issue), pages.
   
2. MLA (Modern Language Association)  
   - Author, First. "Title." Journal, vol. #, no. #, Year, pp. ##-##.
   
3. Chicago Manual of Style
   - Author, First. "Title." Journal vol. #, no. # (Year): pages.
   
4. IEEE (Institute of Electrical and Electronics Engineers)
   - [#] A. Author, "Title," Journal, vol. #, no. #, pp. ##-##, Year.
   
5. ACM (Association for Computing Machinery)
   - [#] First Last and First Last. Year. Title. Journal vol, issue (Month Year), pages.

TECHNICAL REQUIREMENTS
---------------------
• Python 3.7 or higher
• Streamlit web framework
• PyPDF2 for PDF processing
• Standard Python libraries (re, requests, urllib, datetime, etc.)

INSTALLATION & SETUP
-------------------
1. Clone or download the project files
2. Install required dependencies:
   pip install streamlit PyPDF2 requests

3. Activate virtual environment (if using):
   source assessment-tool/bin/activate

4. Run the application:
   streamlit run citation_analyzer.py

5. Open web browser to: http://localhost:8501

USAGE INSTRUCTIONS
-----------------
1. **Upload PDF**: Click "Choose a PDF file" and select your academic document

2. **View Content**: Check extracted text in the "Content" tab for accuracy

3. **Analyze In-Text Citations**: Review citations within context sentences

4. **Examine References**: View detected references and their formatting

5. **Citation Analysis**: Get detailed style analysis with:
   - Individual reference style detection
   - Format validation results
   - Component extraction details
   - Style consistency warnings

6. **Download Reports**: Export comprehensive analysis reports for documentation

APPLICATION STRUCTURE
--------------------
The application is organized into 7 logical sections:

1. Configuration & Constants
   - Citation style definitions
   - Rate limiting configuration
   - Application settings

2. Citation Style Definitions  
   - Comprehensive pattern matching for each style
   - Validation rules and requirements
   - Style-specific formatting guidelines

3. Utility Functions
   - Domain extraction and rate limiting
   - Helper functions for processing

4. Text Processing & Extraction
   - PDF text extraction with page separation
   - Smart reference section detection
   - In-text citation identification

5. Citation Style Analysis
   - Automated style detection algorithms
   - Confidence scoring mechanisms
   - Component extraction by style

6. URL & DOI Validation
   - URL cleaning and validation
   - DOI resolution checking
   - Error handling for network requests

7. UI Display Functions
   - Professional result presentation
   - Report generation and formatting
   - User interface components

KEY ALGORITHMS
--------------
• Smart Reference Detection: Identifies reference sections by detecting academic 
  section headers at page boundaries and intelligently separating content

• Style Detection Engine: Uses multi-pattern matching with confidence scoring
  to identify citation styles based on formatting patterns, punctuation, and structure

• Component Extraction: Style-specific parsing algorithms extract bibliographic
  components (authors, titles, years, etc.) for detailed analysis

• Format Validation: Rule-based validation checks citations against academic
  style guidelines and reports errors/warnings

VALIDATION FEATURES
------------------
✓ Missing author information detection
✓ Publication year validation and formatting
✓ Title presence and formatting checks
✓ Style-specific punctuation validation
✓ Reference completeness assessment
✓ Style consistency across document
✓ Google Scholar verification links

OUTPUT & REPORTING
-----------------
The tool generates comprehensive reports including:
• Total reference count and distribution
• Citation style breakdown with percentages
• Individual reference analysis with confidence scores
• Format validation results with specific errors
• Component extraction details
• Style consistency warnings
• Downloadable text reports for documentation

PROFESSIONAL USE CASES
---------------------
🎓 Academic Research: Validate citations in research papers and dissertations
📚 Educational Assessment: Check student paper citation quality and consistency  
📝 Manuscript Review: Verify reference formatting before journal submission
🔍 Quality Assurance: Systematic citation analysis for institutional standards
📊 Style Compliance: Ensure adherence to specific academic style guidelines

LIMITATIONS & CONSIDERATIONS
---------------------------
• PDF quality affects text extraction accuracy
• Complex citation formats may require manual verification
• Style detection confidence varies with citation complexity
• Network-dependent features require internet connectivity
• Rate limiting prevents excessive external service calls

TROUBLESHOOTING
--------------
Common Issues:
• No references found: Check PDF has extractable text and clear reference section
• Low confidence scores: Complex or non-standard citation formats may need manual review
• Style inconsistencies: Mixed citation styles require editorial attention
• Network errors: Check internet connection for external validation features

For best results:
• Use PDFs with clear, machine-readable text
• Ensure reference sections are clearly marked
• Verify citations follow standard academic formats
• Use consistent citation style throughout document

TECHNICAL SUPPORT
----------------
This tool is designed for academic and research purposes. For technical issues:
1. Verify PDF quality and text extractability
2. Check citation format against standard style guides  
3. Review debug information in application tabs
4. Use manual verification options when automated detection fails

==============================================================================
Created for academic excellence and citation quality assurance.