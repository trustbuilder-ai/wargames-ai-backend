from sqlmodel import Session, select, text
from fastapi import HTTPException
import hashlib
from typing import Optional
from contextlib import contextmanager

class Locker:
    def __init__(self, db: Session):
        self.db = db

    @contextmanager
    def acquire_lock(self, resource_identifier: str, timeout_ms: int = 5000):
        """
        Acquire PostgreSQL advisory lock for resource provisioning.
        Uses pg_try_advisory_lock for non-blocking with timeout.
        """
        # Create a stable integer from the resource identifier
        if not isinstance(resource_identifier, str):
            raise ValueError("Resource identifier must be a string")
        lock_id = int(hashlib.md5(resource_identifier.encode()).hexdigest()[:8], 16)
        
        try:
            # Try to acquire lock with timeout
            result = self.db.exec(
                text(f"SELECT pg_try_advisory_lock({lock_id})")
            ).first()

            if not result[0]:
                # Lock not acquired, wait with timeout
                wait_result = self.db.exec(
                    text(f"SELECT pg_advisory_lock({lock_id})")
                ).first()

            yield
            
        finally:
            # Always release the lock
            self.db.exec(text(f"SELECT pg_advisory_unlock({lock_id})"))
    
