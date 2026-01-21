"""
Publish Ledger - File-based storage for publish records.

Provides idempotent tracking of spec publications to external systems.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from canonical.config import config


class LedgerStatus(str):
    """Status of a ledger record."""
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class LedgerRecord(BaseModel):
    """A single publish ledger record."""
    ledger_id: str = Field(..., description="Unique ledger record ID")
    feature_id: str = Field(..., description="Feature identifier")
    target: str = Field(..., description="Target system (e.g., feishu)")
    spec_version: str = Field(..., description="Spec version that was published")
    external_id: str = Field(..., description="ID in the external system")
    operation: str = Field(..., description="Operation: created, updated, noop")
    published_at: datetime = Field(default_factory=datetime.utcnow, description="Publication time")
    status: str = Field(LedgerStatus.ACTIVE, description="Record status")
    field_map_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Field mapping at publish time")
    mapping_version: str = Field("1.0", description="Mapping config version used")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")

    @property
    def idempotent_key(self) -> str:
        """Get the idempotent key for this record."""
        return f"{self.feature_id}:{self.target}:{self.spec_version}"


class Ledger:
    """
    File-based ledger for tracking publish operations.
    
    Provides idempotency through the key: feature_id + target + spec_version
    
    File structure:
    ledger/
      records.json  # All records in one file for simplicity
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the Ledger.
        
        Args:
            base_dir: Base directory for ledger. Defaults to config.ledger_dir.
        """
        self.base_dir = base_dir or config.ledger_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.records_file = self.base_dir / "records.json"
        self._records: Dict[str, LedgerRecord] = {}
        self._ledger_counter = 0
        self._load()

    def _load(self) -> None:
        """Load records from disk."""
        if not self.records_file.exists():
            return
        
        with open(self.records_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for record_data in data.get("records", []):
            record = LedgerRecord.model_validate(record_data)
            self._records[record.idempotent_key] = record
        
        self._ledger_counter = data.get("counter", 0)

    def _save(self) -> None:
        """Save records to disk."""
        data = {
            "counter": self._ledger_counter,
            "records": [r.model_dump(mode='json') for r in self._records.values()],
        }
        with open(self.records_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def create(
        self,
        feature_id: str,
        target: str,
        spec_version: str,
        external_id: str,
        operation: str,
        field_map_snapshot: Optional[Dict[str, Any]] = None,
        mapping_version: str = "1.0",
    ) -> LedgerRecord:
        """
        Create a new ledger record (idempotent).
        
        If a record with the same key exists and is active, returns it.
        
        Args:
            feature_id: Feature identifier
            target: Target system (e.g., "feishu")
            spec_version: Spec version being published
            external_id: ID in the external system
            operation: Operation type (created, updated)
            field_map_snapshot: Snapshot of field mapping used
            mapping_version: Version of mapping config
            
        Returns:
            The created or existing LedgerRecord
        """
        key = f"{feature_id}:{target}:{spec_version}"
        
        # Check for existing record (idempotency)
        if key in self._records:
            existing = self._records[key]
            if existing.status == LedgerStatus.ACTIVE:
                return existing
        
        # Generate new ledger ID
        self._ledger_counter += 1
        today = datetime.utcnow().strftime("%Y%m%d")
        ledger_id = f"L-{today}-{self._ledger_counter:04d}"
        
        # Create record
        record = LedgerRecord(
            ledger_id=ledger_id,
            feature_id=feature_id,
            target=target,
            spec_version=spec_version,
            external_id=external_id,
            operation=operation,
            field_map_snapshot=field_map_snapshot or {},
            mapping_version=mapping_version,
        )
        
        self._records[key] = record
        self._save()
        
        return record

    def get(
        self,
        feature_id: str,
        target: str,
        spec_version: str,
    ) -> Optional[LedgerRecord]:
        """
        Get a ledger record by idempotent key.
        
        Args:
            feature_id: Feature identifier
            target: Target system
            spec_version: Spec version
            
        Returns:
            The LedgerRecord if found, None otherwise
        """
        key = f"{feature_id}:{target}:{spec_version}"
        return self._records.get(key)

    def get_by_ledger_id(self, ledger_id: str) -> Optional[LedgerRecord]:
        """
        Get a ledger record by its ledger_id.
        
        Args:
            ledger_id: The ledger record ID
            
        Returns:
            The LedgerRecord if found, None otherwise
        """
        for record in self._records.values():
            if record.ledger_id == ledger_id:
                return record
        return None

    def find_by_feature(self, feature_id: str) -> List[LedgerRecord]:
        """
        Find all ledger records for a feature.
        
        Args:
            feature_id: Feature identifier
            
        Returns:
            List of LedgerRecords for the feature
        """
        return [
            r for r in self._records.values()
            if r.feature_id == feature_id
        ]

    def find_by_external_id(self, external_id: str, target: str = "feishu") -> List[LedgerRecord]:
        """
        Find all ledger records for an external ID.
        
        Args:
            external_id: The external system ID
            target: The target system
            
        Returns:
            List of LedgerRecords for the external ID
        """
        return [
            r for r in self._records.values()
            if r.external_id == external_id and r.target == target
        ]

    def find_active_by_feature(self, feature_id: str, target: str = "feishu") -> Optional[LedgerRecord]:
        """
        Find the active ledger record for a feature.
        
        Args:
            feature_id: Feature identifier
            target: Target system
            
        Returns:
            The active LedgerRecord if found, None otherwise
        """
        records = [
            r for r in self._records.values()
            if r.feature_id == feature_id and r.target == target and r.status == LedgerStatus.ACTIVE
        ]
        if not records:
            return None
        # Return the most recent one
        return max(records, key=lambda r: r.published_at)

    def update_status(self, ledger_id: str, status: str) -> Optional[LedgerRecord]:
        """
        Update the status of a ledger record.
        
        Args:
            ledger_id: The ledger record ID
            status: New status
            
        Returns:
            The updated LedgerRecord if found, None otherwise
        """
        record = self.get_by_ledger_id(ledger_id)
        if not record:
            return None
        
        # Update the record in the dict
        key = record.idempotent_key
        self._records[key].status = status
        self._save()
        
        return self._records[key]

    def list_all(self) -> List[LedgerRecord]:
        """
        List all ledger records.
        
        Returns:
            List of all LedgerRecords
        """
        return list(self._records.values())

    def delete(self, ledger_id: str) -> bool:
        """
        Delete a ledger record.
        
        Args:
            ledger_id: The ledger record ID
            
        Returns:
            True if deleted, False if not found
        """
        record = self.get_by_ledger_id(ledger_id)
        if not record:
            return False
        
        key = record.idempotent_key
        del self._records[key]
        self._save()
        
        return True

    def clear(self) -> int:
        """
        Clear all ledger records.
        
        Returns:
            Number of records deleted
        """
        count = len(self._records)
        self._records.clear()
        self._ledger_counter = 0
        self._save()
        return count
