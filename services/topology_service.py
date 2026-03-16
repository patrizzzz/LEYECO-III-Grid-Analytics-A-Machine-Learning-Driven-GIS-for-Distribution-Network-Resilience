from sqlalchemy import text
from extensions import db

class TopologyService:
    """
    High-performance network topology tracing using SQL Recursive CTEs.
    Moves graph traversal into the database engine for maximum speed.
    """

    @staticmethod
    def trace_downstream_sql(start_bus_id):
        """
        Performs a directed downstream trace starting from a bus ID.
        Ensures type consistency for PostgreSQL Recursive CTE.
        """
        query = text("""
            WITH RECURSIVE downstream_trace AS (
                -- 1. Initial set: Explicitly cast to character varying to match table columns
                SELECT CAST(:start_id AS varchar) AS current_bus
                
                UNION
                
                -- 2. Recursive step
                SELECT CAST(connected_bus AS varchar)
                FROM (
                    SELECT to_bus_id AS connected_bus, from_bus_id AS parent_bus FROM distribution_line_segment
                    UNION ALL
                    SELECT to_secondary_bus_id AS connected_bus, from_primary_bus_id AS parent_bus FROM distribution_transformer
                    UNION ALL
                    SELECT to_bus_id AS connected_bus, from_bus_id AS parent_bus FROM secondary_line_segment
                    UNION ALL
                    SELECT to_customer_id AS connected_bus, from_bus_id AS parent_bus FROM secondary_service_drop
                    UNION ALL
                    SELECT to_bus AS connected_bus, from_bus AS parent_bus FROM line_connection
                ) connections
                JOIN downstream_trace dt ON CAST(connections.parent_bus AS varchar) = dt.current_bus
            )
            SELECT DISTINCT current_bus FROM downstream_trace;
        """)
        
        try:
            # We strip to ensure no whitespace causes mismatch
            result = db.session.execute(query, {'start_id': str(start_bus_id).strip()})
            return [row[0] for row in result if row[0]]
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def trace_upstream_sql(start_bus_id):
        """
        Performs a reversed trace to find the path back to the substation/transformer.
        """
        query = text("""
            WITH RECURSIVE upstream_trace AS (
                SELECT CAST(:start_id AS varchar) AS current_bus
                
                UNION
                
                SELECT CAST(parent_bus AS varchar)
                FROM (
                    SELECT from_bus_id AS parent_bus, to_bus_id AS target_bus FROM distribution_line_segment
                    UNION ALL
                    SELECT from_primary_bus_id AS parent_bus, to_secondary_bus_id AS target_bus FROM distribution_transformer
                    UNION ALL
                    SELECT from_bus_id AS parent_bus, to_bus_id AS target_bus FROM secondary_line_segment
                    UNION ALL
                    SELECT from_bus_id AS parent_bus, to_customer_id AS target_bus FROM secondary_service_drop
                    UNION ALL
                    SELECT from_bus AS parent_bus, to_bus AS target_bus FROM line_connection
                ) connections
                JOIN upstream_trace ut ON CAST(connections.target_bus AS varchar) = ut.current_bus
            )
            SELECT DISTINCT current_bus FROM upstream_trace;
        """)
        
        try:
            result = db.session.execute(query, {'start_id': str(start_bus_id).strip()})
            return [row[0] for row in result if row[0]]
        except Exception as e:
            db.session.rollback()
            raise e
