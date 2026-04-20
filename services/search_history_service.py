"""
Search history service layer.
"""
import sqlite3
import json
from utils.db_utils import get_db_connection, close_db_connection


def save_search_history(config_dict, search_name=None):
    """
    Save current search configuration to history.
    
    Args:
        config_dict (dict): Configuration dictionary with search parameters
        search_name (str, optional): Optional name for this search
        
    Returns:
        int: ID of the saved search history entry
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO search_history (
                search_name, search_queries, desc_words, title_exclude,
                title_include, company_exclude, languages, pages_to_scrape,
                rounds, days_to_scrape, timespan, listing_must_include_one_of
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            search_name,
            json.dumps(config_dict.get('search_queries', [])),
            json.dumps(config_dict.get('desc_words', [])),
            json.dumps(config_dict.get('title_exclude', [])),
            json.dumps(config_dict.get('title_include', [])),
            json.dumps(config_dict.get('company_exclude', [])),
            json.dumps(config_dict.get('languages', [])),
            config_dict.get('pages_to_scrape', 10),
            config_dict.get('rounds', 1),
            config_dict.get('days_to_scrape', 10),
            config_dict.get('timespan', ''),
            json.dumps(config_dict.get('listing_must_include_one_of', [])),
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        close_db_connection(conn)


def get_search_history(config_dict, limit=20):
    """
    Get recent search history entries.
    
    Args:
        config_dict (dict): Configuration dictionary
        limit (int): Maximum number of entries to return
        
    Returns:
        list: List of search history dictionaries
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, search_name, search_queries, desc_words, title_exclude,
                   title_include, company_exclude, languages, pages_to_scrape,
                   rounds, days_to_scrape, timespan, listing_must_include_one_of, created_at
            FROM search_history
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        results = cursor.fetchall()
        history = []
        
        for row in results:
            history.append({
                'id': row[0],
                'search_name': row[1],
                'search_queries': json.loads(row[2]) if row[2] else [],
                'desc_words': json.loads(row[3]) if row[3] else [],
                'title_exclude': json.loads(row[4]) if row[4] else [],
                'title_include': json.loads(row[5]) if row[5] else [],
                'company_exclude': json.loads(row[6]) if row[6] else [],
                'languages': json.loads(row[7]) if row[7] else [],
                'pages_to_scrape': row[8],
                'rounds': row[9],
                'days_to_scrape': row[10],
                'timespan': row[11],
                'listing_must_include_one_of': json.loads(row[12]) if row[12] else [],
                'created_at': row[13]
            })
        
        return history
    finally:
        close_db_connection(conn)


def get_search_history_by_id(history_id, config_dict):
    """
    Get a specific search history entry by ID.
    
    Args:
        history_id (int): Search history ID
        config_dict (dict): Configuration dictionary
        
    Returns:
        dict: Search history dictionary, or None if not found
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, search_name, search_queries, desc_words, title_exclude,
                   title_include, company_exclude, languages, pages_to_scrape,
                   rounds, days_to_scrape, timespan, listing_must_include_one_of, created_at
            FROM search_history
            WHERE id = ?
        """, (history_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'search_name': row[1],
                'search_queries': json.loads(row[2]) if row[2] else [],
                'desc_words': json.loads(row[3]) if row[3] else [],
                'title_exclude': json.loads(row[4]) if row[4] else [],
                'title_include': json.loads(row[5]) if row[5] else [],
                'company_exclude': json.loads(row[6]) if row[6] else [],
                'languages': json.loads(row[7]) if row[7] else [],
                'pages_to_scrape': row[8],
                'rounds': row[9],
                'days_to_scrape': row[10],
                'timespan': row[11],
                'listing_must_include_one_of': json.loads(row[12]) if row[12] else [],
                'created_at': row[13]
            }
        return None
    finally:
        close_db_connection(conn)


def delete_search_history(history_id, config_dict):
    """
    Delete a search history entry.
    
    Args:
        history_id (int): Search history ID
        config_dict (dict): Configuration dictionary
        
    Returns:
        bool: True if deleted, False if not found
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM search_history WHERE id = ?", (history_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        close_db_connection(conn)


def clear_search_history(config_dict):
    """
    Clear all search history entries.
    
    Args:
        config_dict (dict): Configuration dictionary
        
    Returns:
        int: Number of entries deleted
    """
    conn = get_db_connection(config_dict=config_dict)
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM search_history")
        conn.commit()
        return cursor.rowcount
    finally:
        close_db_connection(conn)
