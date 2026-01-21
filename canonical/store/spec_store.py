"""
Spec Store - File-based storage for Canonical Specs.

Provides versioned, immutable storage of specs with support for:
- Save with automatic version generation
- Load by feature_id and optional version
- List all versions for a feature
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from canonical.models.spec import CanonicalSpec
from canonical.config import config


class SpecStore:
    """
    File-based storage for Canonical Specs.
    
    Directory structure:
    specs/
      F-2026-001/
        S-20260113-0001.json
        S-20260113-0002.json
      F-2026-002/
        S-20260113-0001.json
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the SpecStore.
        
        Args:
            base_dir: Base directory for specs. Defaults to config.specs_dir.
        """
        self.base_dir = base_dir or config.specs_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._version_counters: Dict[str, int] = {}  # feature_id -> last version number

    def save(self, spec: CanonicalSpec) -> str:
        """
        Save a spec and return the assigned version.
        
        If spec.meta.spec_version is None, generates a new version.
        If spec.meta.spec_version is set, saves with that version (must be new).
        
        Args:
            spec: The CanonicalSpec to save
            
        Returns:
            The spec_version that was saved
            
        Raises:
            ValueError: If the version already exists
        """
        feature_id = spec.feature.feature_id
        feature_dir = self.base_dir / feature_id
        feature_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate or validate version
        if spec.meta.spec_version is None:
            spec_version = self._generate_version(feature_id)
            spec.meta.spec_version = spec_version
        else:
            spec_version = spec.meta.spec_version
            # Check if version already exists
            file_path = feature_dir / f"{spec_version}.json"
            if file_path.exists():
                raise ValueError(f"Version {spec_version} already exists for feature {feature_id}")
        
        # Update timestamps
        spec.feature.updated_at = datetime.utcnow()
        
        # Save to file
        file_path = feature_dir / f"{spec_version}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(spec.model_dump(mode='json'), f, indent=2, ensure_ascii=False, default=str)
        
        return spec_version

    def load(self, feature_id: str, spec_version: Optional[str] = None) -> Optional[CanonicalSpec]:
        """
        Load a spec by feature_id and optional version.
        
        Args:
            feature_id: The feature identifier
            spec_version: Optional specific version. If None, loads latest.
            
        Returns:
            The loaded CanonicalSpec, or None if not found
        """
        feature_dir = self.base_dir / feature_id
        if not feature_dir.exists():
            return None
        
        if spec_version is None:
            # Load latest version
            versions = self.list_versions(feature_id)
            if not versions:
                return None
            spec_version = versions[0]  # Most recent
        
        file_path = feature_dir / f"{spec_version}.json"
        if not file_path.exists():
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return CanonicalSpec.model_validate(data)

    def list_versions(self, feature_id: str) -> List[str]:
        """
        List all versions for a feature, sorted by version (newest first).
        
        Args:
            feature_id: The feature identifier
            
        Returns:
            List of spec_versions, sorted descending (newest first)
        """
        feature_dir = self.base_dir / feature_id
        if not feature_dir.exists():
            return []
        
        versions = []
        for file_path in feature_dir.glob("S-*.json"):
            version = file_path.stem
            versions.append(version)
        
        # Sort descending (newest first) - versions are sortable as strings
        versions.sort(reverse=True)
        return versions

    def list_features(self) -> List[str]:
        """
        List all feature IDs in the store.
        
        Returns:
            List of feature_ids
        """
        features = []
        for path in self.base_dir.iterdir():
            if path.is_dir() and path.name.startswith("F-"):
                features.append(path.name)
        return sorted(features)

    def exists(self, feature_id: str, spec_version: Optional[str] = None) -> bool:
        """
        Check if a spec exists.
        
        Args:
            feature_id: The feature identifier
            spec_version: Optional specific version
            
        Returns:
            True if the spec exists
        """
        feature_dir = self.base_dir / feature_id
        if not feature_dir.exists():
            return False
        
        if spec_version is None:
            # Check if any version exists
            return bool(list(feature_dir.glob("S-*.json")))
        
        file_path = feature_dir / f"{spec_version}.json"
        return file_path.exists()

    def delete(self, feature_id: str, spec_version: Optional[str] = None) -> bool:
        """
        Delete a spec or all specs for a feature.
        
        Args:
            feature_id: The feature identifier
            spec_version: Optional specific version. If None, deletes all.
            
        Returns:
            True if something was deleted
        """
        feature_dir = self.base_dir / feature_id
        if not feature_dir.exists():
            return False
        
        if spec_version is None:
            # Delete entire feature directory
            import shutil
            shutil.rmtree(feature_dir)
            return True
        
        file_path = feature_dir / f"{spec_version}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        
        return False

    def _generate_version(self, feature_id: str) -> str:
        """
        Generate a new version identifier.
        
        Format: S-YYYYMMDD-NNNN where NNNN is a sequential counter.
        """
        today = datetime.utcnow().strftime("%Y%m%d")
        
        # Get the highest existing version number for today
        feature_dir = self.base_dir / feature_id
        prefix = f"S-{today}-"
        
        max_num = 0
        if feature_dir.exists():
            for file_path in feature_dir.glob(f"{prefix}*.json"):
                version = file_path.stem
                try:
                    num = int(version.split("-")[-1])
                    max_num = max(max_num, num)
                except ValueError:
                    continue
        
        # Also check in-memory counter
        counter_key = f"{feature_id}:{today}"
        if counter_key in self._version_counters:
            max_num = max(max_num, self._version_counters[counter_key])
        
        next_num = max_num + 1
        self._version_counters[counter_key] = next_num
        
        return f"S-{today}-{next_num:04d}"

    def generate_feature_id(self) -> str:
        """
        Generate a new feature ID.
        
        Format: F-YYYY-NNN where NNN is a sequential counter.
        """
        year = datetime.utcnow().strftime("%Y")
        prefix = f"F-{year}-"
        
        max_num = 0
        for feature_dir in self.base_dir.iterdir():
            if feature_dir.is_dir() and feature_dir.name.startswith(prefix):
                try:
                    num = int(feature_dir.name.split("-")[-1])
                    max_num = max(max_num, num)
                except ValueError:
                    continue
        
        next_num = max_num + 1
        return f"F-{year}-{next_num:03d}"
