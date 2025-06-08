Assessment Tool
==============================================================================

OVERVIEW
--------
The Assessment Tool includes a PDF Citation Analyzer, which is designed for academic researchers, students, and educators to analyze and validate citations in PDF documents. It provides automated citation style detection, format validation, and comprehensive reporting capabilities.

FEATURES
--------
🔍 Advanced Citation Analysis:

- Automatic detection of 5 major citation styles (APA, MLA, Chicago, IEEE, ACM)
- Confidence scoring for style detection accuracy
- Citation format validation with error reporting
- Component extraction (authors, titles, years, journals, etc.)

📝 Enhanced Text Processing:

- PDF text extraction with page-by-page breakdown
- Advanced reference section detection with flexible header recognition
- Support for multiple reference formats: [1], 1., plain numbers, Author et al.
- Smart separation of body text and references section
- In-text citation detection (numbered and author-year formats)
- Context sentence extraction for citations
- Interactive content editing with real-time re-analysis

📊 Quality Assessment:

- Style consistency analysis across document
- Format compliance checking
- Missing component identification
- Comprehensive validation reporting

🔗 Reference Validation:

- Google Scholar integration for manual verification
- Rate-limited external service calls
- Professional error handling and fallback options

🎛️ Interactive Features:

- Real-time content editing and re-analysis
- Session state management with automatic updates
- Force refresh functionality for widget issues
- Enhanced debugging information for troubleshooting
- Smart pattern filtering for non-reference content

📈 Reporting & Export:

- Detailed citation analysis reports
- Style distribution statistics
- Downloadable analysis results
- Professional formatting and presentation

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
- Python 3.7 or higher
- Streamlit web framework
- PyPDF2 for PDF processing
- Standard Python libraries (re, requests, urllib, datetime, etc.)

INSTALLATION & SETUP
-------------------
1. Clone or download the project files
2. Install required dependencies:
```
   pip install streamlit PyPDF2 requests
```
3. Activate virtual environment (if using):
```
   source assessment-tool/bin/activate
```
4. Run the application:
```
   streamlit run citation_analyzer.py
```
5. Open web browser to: 
```
http://localhost:8501
```

USAGE INSTRUCTIONS
-----------------
1. **Upload PDF**: Click "Choose a PDF file" and select your academic document

2. **View Content**: Check extracted text in the "Content" tab for accuracy
   - Edit content directly in the text area if needed
   - Fix OCR errors, formatting issues, or reference section problems

3. **Interactive Re-analysis**: 
   - Modify content in the editable text area
   - Click "Re-analyze Citations" to update all analysis tabs
   - Use "Force Refresh" if the text area seems unresponsive
   - Click "Reset to Original" to restore the original PDF content

4. **Analyze In-Text Citations**: Review citations within context sentences

5. **Examine References**: View detected references and their formatting
   - Check the "Raw References Text" expander for debugging
   - References update automatically after re-analysis

6. **Citation Analysis**: Get detailed style analysis with:
   - Individual reference style detection
   - Format validation results
   - Component extraction details
   - Style consistency warnings

7. **Download Reports**: Export comprehensive analysis reports for documentation

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

4. Enhanced Text Processing & Extraction
   - PDF text extraction with page separation
   - Advanced reference section detection with flexible header recognition
   - Support for multiple reference formats: [1], 1., plain numbers, Author et al.
   - Smart separation handles page numbers, section headers, and headerless references
   - In-text citation identification
   - Interactive content modification and re-analysis

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
- Advanced Reference Detection: Multi-pass algorithm that:
  - Detects reference headers with various prefixes (page numbers, section numbers)
  - Handles complex formats: "Page 15 References", "7. References", "Appendix A: References"
  - Identifies references without explicit headers using content pattern analysis
  - Supports references anywhere in document, not just at page boundaries

- Enhanced Reference Format Support: Extracts references in multiple formats:
  - Bracketed numbers: [1] Author, A. (2023). Title...
  - Numbered with periods: 1. Author, A. (2023). Title...
  - Plain numbers: 1 Author, A. (2023). Title...
  - Author names: Author, A., Co-author, B. (2023). Title...
  - Et al. format: Authorname et al. (2023). Title...

- Style Detection Engine: Uses multi-pattern matching with confidence scoring
  to identify citation styles based on formatting patterns, punctuation, and structure

- Component Extraction: Style-specific parsing algorithms extract bibliographic
  components (authors, titles, years, etc.) for detailed analysis

- ormat Validation: Rule-based validation checks citations against academic
  style guidelines and reports errors/warnings

VALIDATION FEATURES
------------------
- Missing author information detection
- Publication year validation and formatting
- Title presence and formatting checks
- Style-specific punctuation validation
- Reference completeness assessment
- Style consistency across document
- Google Scholar verification links

OUTPUT & REPORTING
-----------------
The tool generates comprehensive reports including:
- Total reference count and distribution
- Citation style breakdown with percentages
- Individual reference analysis with confidence scores
- Format validation results with specific errors
- Component extraction details
- Style consistency warnings
- Downloadable text reports for documentation

PROFESSIONAL USE CASES
---------------------
🎓 Academic Research: Validate citations in research papers and dissertations

📚 Educational Assessment: Check student paper citation quality and consistency  

📝 Manuscript Review: Verify reference formatting before journal submission

🔍 Quality Assurance: Systematic citation analysis for institutional standards

📊 Style Compliance: Ensure adherence to specific academic style guidelines


LIMITATIONS & CONSIDERATIONS
---------------------------
- PDF quality affects text extraction accuracy
- Complex citation formats may require manual verification
- Style detection confidence varies with citation complexity
- Network-dependent features require internet connectivity
- Rate limiting prevents excessive external service calls

TROUBLESHOOTING
--------------
Common Issues:

- **References not updating**: 
  - Make sure to click "Re-analyze Citations" after editing content
  - Try "Force Refresh" if the text area seems unresponsive
  - Check the debug information for content length changes
- **No references found**: Check PDF has extractable text and reference content (tool now handles headers with page numbers, section numbers, and headerless references)
- **Text area not responding**: Use "Force Refresh" button to reset the widget state
- **Old content persisting**: Click "Reset to Original" to restore the original PDF content
- **Low confidence scores**: Complex or non-standard citation formats may need manual review
- **Style inconsistencies**: Mixed citation styles require editorial attention
- **Network errors**: Check internet connection for external validation features


Interactive Re-analysis Tips:

- Edit content directly in the text area to fix extraction issues
- Add reference headers manually if not detected: "References", "Bibliography"
- Fix concatenated headers: change "19REFERENCES" to "19 REFERENCES"
- Separate merged references into individual lines
- Remove non-reference content like "(No references available)"


For best results:
- Use PDFs with clear, machine-readable text
- Reference sections can now be detected even without clear headers
- Supports various reference formats: [1], 1., plain numbers, Author et al.
- Tool handles prefixed headers like "Page 15 References" or "7. References"
- Use consistent citation style throughout document
- Utilize the interactive editing feature for challenging formats

TECHNICAL SUPPORT
----------------
This tool is designed for academic and research purposes. For technical issues:

1. Verify PDF quality and text extractability
2. Check citation format against standard style guides  
3. Review debug information in application tabs
4. Use manual verification options when automated detection fails


**Created for academic excellence and citation quality assurance.**