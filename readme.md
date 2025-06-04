Assessment tool
---
## Overview
This tool is designed to help assess the quality of a design report or a research paper. 

## Features
- Examines whether there are any plagiarism in the report by comparing the report to a databased of cited papers.
- Examines the citations in the report to ensure that the report is well-cited.
- Examines the images in the report to ensure that they are well-cited.


## How to run the code
source assessment-tool/bin/activate //activate the virtualenv
streamlit run app.py //run the code
deactivate //deactivate the virtualenv



---
## Current Issue:
- validating ACM URLs --> it will be a problem, because the ACM will block my IP address if I try to validate too many URLs in a short period of time.
--> alternative solution: validate the URL format first, if it's a valid format, then I can assume it's a valid URL. And use Google scholar api to verify the reference, instead of accessing the ACM URL directly. (TODO)
