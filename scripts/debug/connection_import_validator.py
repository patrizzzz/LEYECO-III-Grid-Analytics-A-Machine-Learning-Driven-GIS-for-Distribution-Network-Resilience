"""
Validation module for user-defined network connection imports.

Validates connections before inserting into the database:
- Both From_ID and To_ID must exist as bus IDs in Post table
- Reject self-connections (From_ID = To_ID)
- Enforce feeder/circuit consistency where applicable
- Allow connections on the same pole only if Pole_Number matches
- Enforce bus-type compatibility rules
- Prevent duplicate edges
"""

from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Set


class ConnectionValidationError(Exception):
    """Raised when a connection fails validation."""
    pass


class ConnectionValidator:
    """Validates network connections against database constraints and business rules."""

    def __init__(self, session, Post, LineConnection):
        """
        Initialize validator with database session and models.
        
        Args:
            session: SQLAlchemy session
            Post: Post model class
            LineConnection: LineConnection model class
        """
        self.session = session
        self.Post = Post
        self.LineConnection = LineConnection
        
        # Cache: bus_id -> post info
        self._bus_cache: Dict[str, Dict] = {}
        # Cache: existing connections (from_bus, to_bus, connection_type) -> True
        self._existing_connections: Set[Tuple[str, str, str]] = set()
        
        self._build_bus_cache()
        self._build_existing_connections_cache()

    def _build_bus_cache(self):
        """Build cache of all bus IDs -> post information."""
        posts = self.session.query(
            self.Post.id,
            self.Post.pole_number,
            self.Post.feeder,
            self.Post.circuit,
            self.Post.primary_bus_id,
            self.Post.transformer_bus_id,
            self.Post.sec_bus_id,
        ).all()
        
        for post in posts:
            post_info = {
                'post_id': post.id,
                'pole_number': post.pole_number,
                'feeder': post.feeder,
                'circuit': post.circuit,
            }
            
            # Map each bus ID to its post info
            if post.primary_bus_id:
                bus_id = str(post.primary_bus_id).strip()
                if bus_id:
                    self._bus_cache[bus_id] = {**post_info, 'bus_type': 'Primary'}
            
            if post.transformer_bus_id:
                bus_id = str(post.transformer_bus_id).strip()
                if bus_id:
                    self._bus_cache[bus_id] = {**post_info, 'bus_type': 'Transformer'}
            
            if post.sec_bus_id:
                bus_id = str(post.sec_bus_id).strip()
                if bus_id:
                    self._bus_cache[bus_id] = {**post_info, 'bus_type': 'Secondary'}

    def _build_existing_connections_cache(self):
        """Build cache of existing connections to prevent duplicates."""
        connections = self.session.query(
            self.LineConnection.from_bus,
            self.LineConnection.to_bus,
            self.LineConnection.connection_type,
        ).all()
        
        for conn in connections:
            key = (
                str(conn.from_bus).strip(),
                str(conn.to_bus).strip(),
                str(conn.connection_type).strip()
            )
            self._existing_connections.add(key)

    def _get_bus_type(self, bus_id: str) -> Optional[str]:
        """Get bus type (Primary, Transformer, Secondary) for a bus ID."""
        bus_info = self._bus_cache.get(bus_id)
        return bus_info.get('bus_type') if bus_info else None

    def _get_post_info(self, bus_id: str) -> Optional[Dict]:
        """Get post information for a bus ID."""
        return self._bus_cache.get(bus_id)

    def _normalize_connection_type(self, conn_type: str) -> str:
        """Normalize connection type string."""
        if not conn_type:
            return ""
        s = str(conn_type).strip()
        # Standardize common variations
        s = s.replace(" ", "_").replace("-", "_")
        if s.lower() in ["primary_to_primary", "primary-primary", "primary_primary"]:
            return "Primary_to_Primary"
        if s.lower() in ["primary_to_transformer", "primary-transformer", "primary_transformer"]:
            return "Primary_to_Transformer"
        if s.lower() in ["transformer_to_secondary", "transformer-secondary", "transformer_secondary"]:
            return "Transformer_to_Secondary"
        if s.lower() in ["secondary_to_secondary", "secondary-secondary", "secondary_secondary"]:
            return "Secondary_to_Secondary"
        return s

    def _validate_bus_type_compatibility(self, from_bus_type: str, to_bus_type: str, connection_type: str) -> bool:
        """
        Validate bus-type compatibility rules:
        - Primary ↔ Primary → allowed
        - Primary ↔ Transformer → allowed
        - Transformer ↔ Secondary → allowed
        - Invalid combinations → reject
        """
        conn_type_norm = self._normalize_connection_type(connection_type)
        
        # Primary ↔ Primary
        if conn_type_norm == "Primary_to_Primary":
            return from_bus_type == "Primary" and to_bus_type == "Primary"
        
        # Primary ↔ Transformer
        if conn_type_norm == "Primary_to_Transformer":
            return (from_bus_type == "Primary" and to_bus_type == "Transformer") or \
                   (from_bus_type == "Transformer" and to_bus_type == "Primary")
        
        # Transformer ↔ Secondary
        if conn_type_norm == "Transformer_to_Secondary":
            return (from_bus_type == "Transformer" and to_bus_type == "Secondary") or \
                   (from_bus_type == "Secondary" and to_bus_type == "Transformer")
        
        # Secondary ↔ Secondary
        if conn_type_norm == "Secondary_to_Secondary":
            return from_bus_type == "Secondary" and to_bus_type == "Secondary"
        
        # Unknown connection type - allow if bus types match
        return True

    def validate_connection(self, from_id: str, to_id: str, connection_type: str, 
                           feeder: Optional[str] = None, circuit: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate a single connection.
        
        Returns:
            (is_valid, error_message)
        """
        from_id = str(from_id).strip() if from_id else ""
        to_id = str(to_id).strip() if to_id else ""
        connection_type = str(connection_type).strip() if connection_type else ""
        
        # Rule 1: Both IDs must be non-empty
        if not from_id:
            return False, "From_ID is empty"
        if not to_id:
            return False, "To_ID is empty"
        if not connection_type:
            return False, "Connection_Type is empty (required)"
        
        # Rule 2: Reject self-connections
        if from_id == to_id:
            return False, f"Self-connection not allowed: From_ID={from_id}, To_ID={to_id}"
        
        # Rule 3: Both bus IDs must exist
        from_info = self._get_post_info(from_id)
        to_info = self._get_post_info(to_id)
        
        if not from_info:
            return False, f"From_ID '{from_id}' does not exist in database (not found as Primary Bus ID, Transformer Bus ID, or Secondary Bus ID)"
        
        if not to_info:
            return False, f"To_ID '{to_id}' does not exist in database (not found as Primary Bus ID, Transformer Bus ID, or Secondary Bus ID)"
        
        # Rule 4: Same pole connections - only allow if Pole_Number matches
        if from_info['post_id'] == to_info['post_id']:
            if from_info['pole_number'] != to_info['pole_number']:
                return False, f"Same post connection but pole numbers differ: From pole={from_info['pole_number']}, To pole={to_info['pole_number']}"
        
        # Rule 5: Bus-type compatibility
        from_bus_type = from_info.get('bus_type')
        to_bus_type = to_info.get('bus_type')
        
        if not self._validate_bus_type_compatibility(from_bus_type, to_bus_type, connection_type):
            return False, f"Invalid bus-type combination: From '{from_bus_type}' → To '{to_bus_type}' for connection type '{connection_type}'"
        
        # Rule 6: Feeder/circuit consistency (where applicable)
        from_feeder = from_info.get('feeder')
        from_circuit = from_info.get('circuit')
        to_feeder = to_info.get('feeder')
        to_circuit = to_info.get('circuit')
        
        conn_type_norm = self._normalize_connection_type(connection_type)
        
        # Enforce feeder/circuit consistency for Primary_to_Primary connections
        if conn_type_norm == "Primary_to_Primary":
            if from_feeder and to_feeder and from_feeder != to_feeder:
                return False, f"Cross-feeder connection not allowed for Primary_to_Primary: From feeder={from_feeder}, To feeder={to_feeder}"
            if from_circuit and to_circuit and from_circuit != to_circuit:
                return False, f"Cross-circuit connection not allowed for Primary_to_Primary: From circuit={from_circuit}, To circuit={to_circuit}"
        
        # If feeder/circuit provided in import, validate consistency
        if feeder:
            if from_feeder and from_feeder != feeder:
                return False, f"Feeder mismatch: From bus has feeder={from_feeder}, but import specifies feeder={feeder}"
            if to_feeder and to_feeder != feeder:
                return False, f"Feeder mismatch: To bus has feeder={to_feeder}, but import specifies feeder={feeder}"
        
        if circuit:
            if from_circuit and from_circuit != circuit:
                return False, f"Circuit mismatch: From bus has circuit={from_circuit}, but import specifies circuit={circuit}"
            if to_circuit and to_circuit != circuit:
                return False, f"Circuit mismatch: To bus has circuit={to_circuit}, but import specifies circuit={circuit}"
        
        # Rule 7: Prevent duplicate edges (exact match only, not reverse)
        conn_type_norm = self._normalize_connection_type(connection_type)
        duplicate_key = (from_id, to_id, conn_type_norm)
        if duplicate_key in self._existing_connections:
            return False, f"Duplicate connection already exists: {from_id} → {to_id} ({conn_type_norm})"
        
        return True, None

    def validate_batch(self, connections: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate a batch of connections.
        
        Args:
            connections: List of dicts with keys: From_ID, To_ID, Connection_Type, 
                        optionally Feeder, Circuit
        
        Returns:
            (valid_connections, invalid_connections)
            valid_connections: List of validated connection dicts ready for insertion
            invalid_connections: List of dicts with 'error' field explaining why invalid
        """
        valid = []
        invalid = []
        
        for idx, conn in enumerate(connections):
            from_id = conn.get('From_ID') or conn.get('from_id') or conn.get('From_ID')
            to_id = conn.get('To_ID') or conn.get('to_id') or conn.get('To_ID')
            conn_type = conn.get('Connection_Type') or conn.get('connection_type') or conn.get('Connection_Type')
            feeder = conn.get('Feeder') or conn.get('feeder')
            circuit = conn.get('Circuit') or conn.get('circuit')
            
            is_valid, error_msg = self.validate_connection(from_id, to_id, conn_type, feeder, circuit)
            
            if is_valid:
                # Normalize connection type and prepare for insertion
                conn_type_norm = self._normalize_connection_type(conn_type)
                
                # Get feeder/circuit from post info if not provided
                from_info = self._get_post_info(from_id)
                to_info = self._get_post_info(to_id)
                
                valid_conn = {
                    'from_bus': from_id,
                    'to_bus': to_id,
                    'connection_type': conn_type_norm,
                    'feeder': feeder or from_info.get('feeder') or to_info.get('feeder'),
                    'circuit': circuit or from_info.get('circuit') or to_info.get('circuit'),
                }
                valid.append(valid_conn)
                
                # Add to existing connections cache to prevent duplicates within batch
                self._existing_connections.add((from_id, to_id, conn_type_norm))
            else:
                invalid.append({
                    'row': idx + 1,  # 1-indexed for user-friendly error messages
                    'from_id': from_id,
                    'to_id': to_id,
                    'connection_type': conn_type,
                    'error': error_msg,
                })
        
        return valid, invalid
