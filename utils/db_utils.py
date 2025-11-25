"""
Database connection utilities.
"""
import sqlite3
from utils.config_utils import load_config


def get_db_connection(config_path='config.json', config_dict=None):
    """
    Get a database connection using the configuration.
    
    Args:
        config_path (str): Path to config file (if config_dict not provided)
        config_dict (dict): Configuration dictionary (optional, overrides config_path)
        
    Returns:
        sqlite3.Connection: Database connection object
    """
    if config_dict is None 
        config = load_config(config_path)
    else:
        config = config_dict
    
    return sqlite3.connect(config["db_path"])


def close_db_connection(conn):
    """
    Close a database connection.
    
    Args:
        conn (sqlite3.Connection): Database connection to close
    """
    if conn:
        conn.close()

