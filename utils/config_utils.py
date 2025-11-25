"""
Configuration utilities.
"""
import json


def load_config(file_name):
    """
    Load configuration from a JSON file.
    
    Args:
        file_name (str): Path to the configuration JSON file
        
    Returns:
        dict: Configuration dictionary
    """
    with open(file_name) as f:
        return json.load(f)


