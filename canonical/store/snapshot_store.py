"""
Snapshot Store - File-based storage for Step Snapshots.

Provides storage for pipeline execution snapshots for audit and replay.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from canonical.models.snapshot import StepSnapshot
from canonical.config import config


class SnapshotStore:
    """
    File-based storage for Step Snapshots.
    
    Directory structure:
    snapshots/
      R-20260113-0001/
        step_001_ingest.json
        step_002_compile.json
      R-20260113-0002/
        step_001_ingest.json
    """
    
    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the SnapshotStore.
        
        Args:
            base_dir: Base directory for snapshots. Defaults to config.snapshots_dir.
        """
        self.base_dir = base_dir or config.snapshots_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._run_counters: Dict[str, int] = {}  # date -> last run number

    def save(self, snapshot: StepSnapshot) -> str:
        """
        Save a step snapshot.
        
        Args:
            snapshot: The StepSnapshot to save
            
        Returns:
            The file path where the snapshot was saved
        """
        run_dir = self.base_dir / snapshot.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Create filename with sequence number and step name
        filename = f"step_{snapshot.step.seq:03d}_{snapshot.step.name.value}.json"
        file_path = run_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot.model_dump(mode='json'), f, indent=2, ensure_ascii=False, default=str)
        
        return str(file_path)

    def load(self, run_id: str, step_seq: int) -> Optional[StepSnapshot]:
        """
        Load a specific step snapshot.
        
        Args:
            run_id: The run identifier
            step_seq: The step sequence number
            
        Returns:
            The loaded StepSnapshot, or None if not found
        """
        run_dir = self.base_dir / run_id
        if not run_dir.exists():
            return None
        
        # Find file with matching sequence number
        pattern = f"step_{step_seq:03d}_*.json"
        files = list(run_dir.glob(pattern))
        if not files:
            return None
        
        with open(files[0], 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return StepSnapshot.model_validate(data)

    def load_by_name(self, run_id: str, step_name: str) -> Optional[StepSnapshot]:
        """
        Load a step snapshot by step name.
        
        Args:
            run_id: The run identifier
            step_name: The step name
            
        Returns:
            The loaded StepSnapshot, or None if not found
        """
        run_dir = self.base_dir / run_id
        if not run_dir.exists():
            return None
        
        # Find file with matching step name
        pattern = f"step_*_{step_name}.json"
        files = list(run_dir.glob(pattern))
        if not files:
            return None
        
        # Return the most recent one (highest sequence number)
        files.sort(reverse=True)
        with open(files[0], 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return StepSnapshot.model_validate(data)

    def list_snapshots(self, run_id: str) -> List[StepSnapshot]:
        """
        List all snapshots for a run, sorted by sequence number.
        
        Args:
            run_id: The run identifier
            
        Returns:
            List of StepSnapshots, sorted by sequence number (ascending)
        """
        run_dir = self.base_dir / run_id
        if not run_dir.exists():
            return []
        
        snapshots = []
        for file_path in sorted(run_dir.glob("step_*.json")):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            snapshots.append(StepSnapshot.model_validate(data))
        
        return snapshots

    def list_runs(self) -> List[str]:
        """
        List all run IDs in the store.
        
        Returns:
            List of run_ids, sorted descending (newest first)
        """
        runs = []
        for path in self.base_dir.iterdir():
            if path.is_dir() and path.name.startswith("R-"):
                runs.append(path.name)
        return sorted(runs, reverse=True)

    def list_runs_for_feature(self, feature_id: str) -> List[str]:
        """
        List all runs for a specific feature.
        
        Args:
            feature_id: The feature identifier
            
        Returns:
            List of run_ids for the feature
        """
        matching_runs = []
        for run_id in self.list_runs():
            # Check first snapshot to see if it matches the feature
            snapshots = self.list_snapshots(run_id)
            if snapshots and snapshots[0].feature_id == feature_id:
                matching_runs.append(run_id)
        return matching_runs

    def exists(self, run_id: str) -> bool:
        """
        Check if a run exists.
        
        Args:
            run_id: The run identifier
            
        Returns:
            True if the run exists
        """
        run_dir = self.base_dir / run_id
        return run_dir.exists()

    def delete(self, run_id: str) -> bool:
        """
        Delete all snapshots for a run.
        
        Args:
            run_id: The run identifier
            
        Returns:
            True if something was deleted
        """
        run_dir = self.base_dir / run_id
        if not run_dir.exists():
            return False
        
        import shutil
        shutil.rmtree(run_dir)
        return True

    def generate_run_id(self) -> str:
        """
        Generate a new run ID.
        
        Format: R-YYYYMMDD-NNNN where NNNN is a sequential counter.
        """
        today = datetime.utcnow().strftime("%Y%m%d")
        prefix = f"R-{today}-"
        
        max_num = 0
        for run_dir in self.base_dir.iterdir():
            if run_dir.is_dir() and run_dir.name.startswith(prefix):
                try:
                    num = int(run_dir.name.split("-")[-1])
                    max_num = max(max_num, num)
                except ValueError:
                    continue
        
        # Also check in-memory counter
        if today in self._run_counters:
            max_num = max(max_num, self._run_counters[today])
        
        next_num = max_num + 1
        self._run_counters[today] = next_num
        
        return f"R-{today}-{next_num:04d}"
