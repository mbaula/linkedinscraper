"""
PDF processing utilities.
"""
from pdfminer.high_level import extract_text


def read_pdf(file_path):
    """
    Read text content from a PDF file.
    
    Args:
        file_path (str): Path to the PDF file
        
    Returns:
        str: Extracted text content, or None if an error occurred
    """
    try:
        text = extract_text(file_path)
        return text
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return None
    except Exception as e:
        print(f"An error occurred while reading the PDF: {e}")
        return None


