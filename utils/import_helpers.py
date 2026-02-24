import re

def normalize_column_name(name):
    """Normalize column name for flexible matching.

    - Lowercase
    - Collapse any non-alphanumeric (spaces, punctuation, parentheses) to single underscores
    - Trim leading/trailing underscores

    This makes headers like 'Length         (meters)' normalize to 'length_meters',
    which can match our DB fields like 'length_meters'.
    """
    if not name:
        return ""
    text = str(name).strip().lower()
    # Replace any run of non-alphanumeric chars with a single underscore
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')

def find_column_value(row, possible_names, header_map=None):
    """
    Find column value using flexible matching of column names.
    Works with both dict rows (CSV) and tuple rows (Excel).
    """
    if not row or not possible_names:
        return None
    
    # For CSV (dict) rows
    if isinstance(row, dict):
        normalized_targets = [normalize_column_name(n) for n in possible_names]
        for key in row.keys():
            normalized_key = normalize_column_name(key)
            if normalized_key in normalized_targets:
                val = row[key]
                return str(val).strip() if val else None
    
    # For Excel (tuple) rows with header_map
    elif header_map:
        for name in possible_names:
            normalized_name = normalize_column_name(name)
            for header_key, idx in header_map.items():
                if normalize_column_name(header_key) == normalized_name:
                    if 0 <= idx < len(row):
                        val = row[idx]
                        return str(val).strip() if val else None
    
    return None

def sanitize_float(value):
    """Convert value to float, return None if invalid"""
    if not value or str(value).strip() == '':
        return None
    try:
        return float(value)
    except (ValueError, AttributeError, TypeError):
        return None
