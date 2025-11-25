"""
Text processing and formatting utilities.
"""
import re


def format_cover_letter_for_latex(cover_letter_text):
    """
    Format cover letter text for LaTeX insertion.
    Extracts body paragraphs and formats them with \noindent and \vspace{1em}
    
    Args:
        cover_letter_text (str): The cover letter text to format
        
    Returns:
        str: LaTeX-formatted cover letter text
    """
    if not cover_letter_text:
        return ""
    
    # Split into paragraphs (double newlines)
    paragraphs = cover_letter_text.split('\n\n')
    
    # Filter out empty paragraphs and common headers/footers
    body_paragraphs = []
    skip_patterns = [
        r'^Dear\s+',
        r'^Sincerely',
        r'^Best regards',
        r'^Regards',
        r'^Thank you for considering',
        r'^I look forward to',
        r'^Please feel free to contact',
        r'^Mark Baula$',
        r'^[A-Z][a-z]+\s+[A-Z][a-z]+$',  # Name signatures
    ]
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # Skip if it matches a header/footer pattern
        should_skip = False
        for pattern in skip_patterns:
            if re.match(pattern, para, re.IGNORECASE):
                should_skip = True
                break
        
        if not should_skip and len(para) > 20:  # Only include substantial paragraphs
            # Escape LaTeX special characters
            para = para.replace('\\', '\\textbackslash{}')
            para = para.replace('&', '\\&')
            para = para.replace('%', '\\%')
            para = para.replace('$', '\\$')
            para = para.replace('#', '\\#')
            para = para.replace('^', '\\textasciicircum{}')
            para = para.replace('_', '\\_')
            para = para.replace('{', '\\{')
            para = para.replace('}', '\\}')
            para = para.replace('~', '\\textasciitilde{}')
            
            body_paragraphs.append(para)
    
    # Format for LaTeX
    latex_formatted = ""
    for para in body_paragraphs:
        latex_formatted += f"\\noindent {para} \\vspace{{1em}}\n\n"
    
    return latex_formatted.strip()


def escape_xml_text(text):
    """
    Escape special characters for XML/HTML (used by ReportLab Paragraph).
    Handles dashes, quotes, and other special characters properly.
    ReportLab's Paragraph uses XML/HTML markup, so we need to escape properly.
    
    Args:
        text (str): Text to escape
        
    Returns:
        str: Escaped text with Unicode dashes normalized to ASCII hyphens
    """
    if not text:
        return ""
    
    # Convert all Unicode dash/hyphen variants to regular ASCII hyphens
    # This prevents rendering issues in PDF
    text = text.replace('\u2011', '-')  # Non-breaking hyphen (‑) U+2011
    text = text.replace('\u2012', '-')  # Figure dash (‒) U+2012
    text = text.replace('\u2013', '-')  # En dash (–) U+2013
    text = text.replace('\u2014', '-')  # Em dash (—) U+2014
    text = text.replace('\u2015', '-')  # Horizontal bar (―) U+2015
    text = text.replace('\u2212', '-')  # Minus sign (−) U+2212
    text = text.replace('\uFE58', '-')  # Small em dash (﹘) U+FE58
    text = text.replace('\uFE63', '-')  # Small hyphen-minus (﹣) U+FE63
    text = text.replace('\uFF0D', '-')  # Full-width hyphen-minus (－) U+FF0D
    
    # Keep regular ASCII hyphens (-) as is
    
    # Escape XML/HTML special characters (must escape & first!)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&apos;')
    
    return text


def normalize_dashes_for_docx(text):
    """
    Convert all Unicode dash variants to regular hyphens for DOCX.
    
    Args:
        text (str): Text to normalize
        
    Returns:
        str: Text with all Unicode dashes converted to ASCII hyphens
    """
    if not text:
        return ""
    
    # Convert all Unicode dash/hyphen variants to regular ASCII hyphens
    text = text.replace('\u2011', '-')  # Non-breaking hyphen (‑) U+2011
    text = text.replace('\u2012', '-')  # Figure dash (‒) U+2012
    text = text.replace('\u2013', '-')  # En dash (–) U+2013
    text = text.replace('\u2014', '-')  # Em dash (—) U+2014
    text = text.replace('\u2015', '-')  # Horizontal bar (―) U+2015
    text = text.replace('\u2212', '-')  # Minus sign (−) U+2212
    text = text.replace('\uFE58', '-')  # Small em dash (﹘) U+FE58
    text = text.replace('\uFE63', '-')  # Small hyphen-minus (﹣) U+FE63
    text = text.replace('\uFF0D', '-')  # Full-width hyphen-minus (－) U+FF0D
    
    return text


def post_process_cover_letter(text):
    """
    Post-process cover letter to fix common issues:
    - Remove all Unicode dash variants
    - Fix percentage spacing (remove space before %)
    - Convert bullet-point style to narrative
    - Clean up formatting
    
    Args:
        text (str): Cover letter text to process
        
    Returns:
        str: Processed cover letter text
    """
    if not text:
        return text
    
    # Replace ALL Unicode dash/hyphen variants with regular hyphens
    dash_replacements = {
        '\u2011': '-',  # Non-breaking hyphen (‑)
        '\u2012': '-',  # Figure dash (‒)
        '\u2013': '-',  # En dash (–)
        '\u2014': '-',  # Em dash (—)
        '\u2015': '-',  # Horizontal bar (―)
        '\u2212': '-',  # Minus sign (−)
        '\uFE58': '-',  # Small em dash (﹘)
        '\uFE63': '-',  # Small hyphen-minus (﹣)
        '\uFF0D': '-',  # Full-width hyphen-minus (－)
    }
    
    for unicode_char, replacement in dash_replacements.items():
        text = text.replace(unicode_char, replacement)
    
    # Fix percentage spacing - remove space before % sign
    # Matches patterns like "90 %", "75 %", etc. and converts to "90%", "75%"
    text = re.sub(r'(\d+)\s+%', r'\1%', text)
    
    # Remove bullet points and convert to narrative
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Remove bullet point markers
        if line.startswith('•') or line.startswith('-') or line.startswith('*') or line.startswith('·'):
            line = line[1:].strip()
        # Remove numbered lists
        if line and line[0].isdigit() and ('.' in line[:3] or ')' in line[:3]):
            # Remove number prefix
            line = re.sub(r'^\d+[\.\)]\s*', '', line)
        
        if line:
            cleaned_lines.append(line)
    
    # Join back into paragraphs
    text = '\n\n'.join(cleaned_lines)
    
    # Remove excessive spacing
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text


