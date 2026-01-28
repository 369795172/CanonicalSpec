"""
Feishu Publisher - Adapter for publishing specs to Feishu (Lark Base).

Implements the publish contract from 04_feishu_publish_contract.md.
"""

import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from jinja2 import Template
import requests

from canonical.models.spec import CanonicalSpec, FeatureStatus
from canonical.store.ledger import Ledger, LedgerRecord, LedgerStatus
from canonical.config import config


class MappingConfig:
    """Configuration for field mapping."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Load mapping configuration from YAML file.
        
        Args:
            config_path: Path to mapping config YAML
        """
        self.config_path = config_path or config.mapping_config_path
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load configuration from file."""
        if self.config_path and self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            # Use default configuration
            self._config = self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        """Return default mapping configuration."""
        return {
            "mapping_version": "1.0",
            "target": {
                "system": "feishu",
                "base_token": config.feishu_base_token or "",
                "table_id": config.feishu_table_id or "",
            },
            "field_mappings": [
                {
                    "feishu_field": "反馈问题",
                    "spec_path": "feature.title",
                    "transform": "direct",
                    "required": True,
                },
                {
                    "feishu_field": "用户故事",
                    "spec_path": "spec.goal",
                    "transform": "template",
                    "template": self._default_user_story_template(),
                    "required": True,
                },
                {
                    "feishu_field": "评审",
                    "spec_path": None,
                    "transform": "fixed",
                    "fixed_value": "审阅",
                    "required": True,
                },
                {
                    "feishu_field": "排期",
                    "spec_path": None,
                    "transform": "fixed",
                    "fixed_value": "排期",
                    "required": True,
                },
                {
                    "feishu_field": "需求状态",
                    "spec_path": None,
                    "transform": "fixed",
                    "fixed_value": "待排期",
                    "required": True,
                },
                {
                    "feishu_field": "需求负责人",
                    "spec_path": "project_context_ref.mentor_user_id",
                    "transform": "direct",
                    "required": False,
                    "default": [],
                },
                {
                    "feishu_field": "执行成员",
                    "spec_path": "project_context_ref.intern_user_id",
                    "transform": "direct",
                    "required": False,
                    "default": [],
                },
                {
                    "feishu_field": "优先级",
                    "spec_path": None,
                    "transform": "fixed",
                    "fixed_value": "中",
                    "required": True,
                },
                {
                    "feishu_field": "需求类型",
                    "spec_path": None,
                    "transform": "fixed",
                    "fixed_value": "新功能",
                    "required": True,
                },
                {
                    "feishu_field": "所属项目",
                    "spec_path": "project_context_ref.project_record_id",
                    "transform": "direct",
                    "required": False,
                },
            ],
        }

    def _default_user_story_template(self) -> str:
        """Return default user story template."""
        return """---
feature_id: {{ feature.feature_id }}
spec_version: {{ meta.spec_version }}
---
{% if spec.background %}
**背景**:
{{ spec.background }}

{% endif %}
**目标**:
{{ spec.goal }}

**非目标**:
{% for ng in spec.non_goals %}- {{ ng }}
{% endfor %}

**验收标准**:
{% for ac in spec.acceptance_criteria %}- {{ ac.id }}: {{ ac.criteria }}
{% endfor %}

**任务列表**:
{% for task in planning.tasks %}- {{ task.task_id }}: {{ task.title }} ({{ task.type }})
{% endfor %}

**验证要求**:
{% for vv in planning.vv %}- {{ vv.vv_id }}: {{ vv.procedure }}
{% endfor %}"""

    @property
    def version(self) -> str:
        return self._config.get("mapping_version", "1.0")

    @property
    def target(self) -> Dict[str, Any]:
        return self._config.get("target", {})

    @property
    def field_mappings(self) -> List[Dict[str, Any]]:
        return self._config.get("field_mappings", [])


class FeishuClient:
    """
    Client for Feishu (Lark) Bitable API.
    
    This is a simplified implementation. In production, use the official SDK.
    """
    
    BASE_URL = "https://open.feishu.cn/open-apis"
    
    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
    ):
        """
        Initialize the Feishu client.
        
        Args:
            app_id: Feishu app ID
            app_secret: Feishu app secret
        """
        self.app_id = app_id or config.feishu_app_id
        self.app_secret = app_secret or config.feishu_app_secret
        
        if not self.app_id or not self.app_secret:
            raise ValueError(
                "Feishu app_id 和 app_secret 必须配置. "
                "设置 CANONICAL_FEISHU_APP_ID 和 CANONICAL_FEISHU_APP_SECRET 环境变量."
            )
        
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    def _get_access_token(self) -> str:
        """Get or refresh access token."""
        now = datetime.utcnow()
        
        if self._access_token and self._token_expires and now < self._token_expires:
            return self._access_token
        
        # Get new token
        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        response = requests.post(url, json={
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        })
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 0:
            raise ValueError(f"Failed to get access token: {data.get('msg')}")
        
        self._access_token = data["tenant_access_token"]
        # Token expires in 2 hours, refresh at 1.5 hours
        from datetime import timedelta
        self._token_expires = now + timedelta(hours=1, minutes=30)
        
        return self._access_token

    def _headers(self) -> Dict[str, str]:
        """Get request headers with auth."""
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    def create_record(
        self,
        base_token: str,
        table_id: str,
        fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a new record in a Bitable table.
        
        Args:
            base_token: Bitable app token
            table_id: Table ID
            fields: Field values
            
        Returns:
            API response with record_id
        """
        url = f"{self.BASE_URL}/bitable/v1/apps/{base_token}/tables/{table_id}/records"
        response = requests.post(url, headers=self._headers(), json={"fields": fields})
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 0:
            raise ValueError(f"Failed to create record: {data.get('msg')}")
        
        return {
            "record_id": data["data"]["record"]["record_id"],
            "fields": data["data"]["record"].get("fields", {}),
        }

    def update_record(
        self,
        base_token: str,
        table_id: str,
        record_id: str,
        fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update an existing record.
        
        Args:
            base_token: Bitable app token
            table_id: Table ID
            record_id: Record ID to update
            fields: Field values to update
            
        Returns:
            API response
        """
        url = f"{self.BASE_URL}/bitable/v1/apps/{base_token}/tables/{table_id}/records/{record_id}"
        response = requests.put(url, headers=self._headers(), json={"fields": fields})
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 0:
            raise ValueError(f"Failed to update record: {data.get('msg')}")
        
        return {
            "record_id": data["data"]["record"]["record_id"],
            "fields": data["data"]["record"].get("fields", {}),
        }

    def get_record(
        self,
        base_token: str,
        table_id: str,
        record_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a record by ID.
        
        Args:
            base_token: Bitable app token
            table_id: Table ID
            record_id: Record ID
            
        Returns:
            Record data or None
        """
        url = f"{self.BASE_URL}/bitable/v1/apps/{base_token}/tables/{table_id}/records/{record_id}"
        response = requests.get(url, headers=self._headers())
        
        if response.status_code == 404:
            return None
        
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 0:
            return None
        
        return data["data"]["record"]


class FeishuPublisher:
    """
    Publisher for Feishu Bitable.
    
    Implements idempotent publish with ledger tracking.
    """
    
    def __init__(
        self,
        ledger: Optional[Ledger] = None,
        client: Optional[FeishuClient] = None,
        mapping_config: Optional[MappingConfig] = None,
    ):
        """
        Initialize the publisher.
        
        Args:
            ledger: Ledger for tracking publishes
            client: Feishu API client
            mapping_config: Field mapping configuration
        """
        self.ledger = ledger or Ledger()
        self._client = client
        self.mapping_config = mapping_config or MappingConfig()

    @property
    def client(self) -> FeishuClient:
        """Get or create Feishu client."""
        if self._client is None:
            self._client = FeishuClient()
        return self._client

    def publish(self, spec: CanonicalSpec) -> Dict[str, Any]:
        """
        Publish a spec to Feishu.
        
        Args:
            spec: The CanonicalSpec to publish (must be executable_ready)
            
        Returns:
            Publish result with operation, external_id, status
            
        Raises:
            ValueError: If spec is not in executable_ready status
        """
        feature_id = spec.feature.feature_id
        spec_version = spec.meta.spec_version
        target = "feishu"
        
        # Check for existing active record (idempotency)
        existing = self.ledger.get(feature_id, target, spec_version)
        if existing and existing.status == LedgerStatus.ACTIVE:
            return {
                "operation": "noop",
                "external_id": existing.external_id,
                "status": "success",
                "spec_version": spec_version,
                "field_map_snapshot": existing.field_map_snapshot,
                "publish_record": existing.model_dump(mode='json'),
            }
        
        # Validate status
        if spec.feature.status != FeatureStatus.EXECUTABLE_READY:
            raise ValueError(
                f"Spec 状态必须是 executable_ready，当前状态: {spec.feature.status}"
            )
        
        # Map fields
        feishu_fields, field_map_snapshot = self._map_fields(spec)
        
        # Check if record already exists for this feature (update case)
        existing_record = self.ledger.find_active_by_feature(feature_id, target)
        
        try:
            if existing_record:
                # Update existing record
                result = self.client.update_record(
                    base_token=self.mapping_config.target.get("base_token"),
                    table_id=self.mapping_config.target.get("table_id"),
                    record_id=existing_record.external_id,
                    fields=feishu_fields,
                )
                operation = "updated"
            else:
                # Create new record
                result = self.client.create_record(
                    base_token=self.mapping_config.target.get("base_token"),
                    table_id=self.mapping_config.target.get("table_id"),
                    fields=feishu_fields,
                )
                operation = "created"
            
            external_id = result["record_id"]
            
            # Mark old record as superseded if updating
            if existing_record:
                self.ledger.update_status(existing_record.ledger_id, LedgerStatus.SUPERSEDED)
            
            # Create new ledger record
            record = self.ledger.create(
                feature_id=feature_id,
                target=target,
                spec_version=spec_version,
                external_id=external_id,
                operation=operation,
                field_map_snapshot=field_map_snapshot,
                mapping_version=self.mapping_config.version,
            )
            
            return {
                "operation": operation,
                "external_id": external_id,
                "status": "success",
                "spec_version": spec_version,
                "field_map_snapshot": field_map_snapshot,
                "publish_record": record.model_dump(mode='json'),
            }
            
        except Exception as e:
            # Record failed attempt
            record = self.ledger.create(
                feature_id=feature_id,
                target=target,
                spec_version=spec_version,
                external_id="",
                operation="failed",
                field_map_snapshot=field_map_snapshot,
                mapping_version=self.mapping_config.version,
            )
            self.ledger.update_status(record.ledger_id, LedgerStatus.FAILED)
            
            raise ValueError(f"发布失败: {str(e)}")

    def _map_fields(self, spec: CanonicalSpec) -> tuple[Dict[str, Any], Dict[str, str]]:
        """
        Map spec fields to Feishu fields.
        
        Returns:
            Tuple of (feishu_fields, field_map_snapshot)
        """
        spec_dict = spec.model_dump()
        feishu_fields = {}
        field_map_snapshot = {}
        
        for mapping in self.mapping_config.field_mappings:
            feishu_field = mapping["feishu_field"]
            transform = mapping.get("transform", "direct")
            spec_path = mapping.get("spec_path")
            
            value = None
            
            if transform == "fixed":
                value = mapping.get("fixed_value")
                field_map_snapshot[feishu_field] = f"fixed:{value}"
            
            elif transform == "direct" and spec_path:
                value = self._get_nested_value(spec_dict, spec_path)
                field_map_snapshot[feishu_field] = spec_path
                
                # Handle person fields (need to wrap in list)
                if feishu_field in ["需求负责人", "执行成员"] and value:
                    if isinstance(value, str):
                        value = [{"id": value}]
                    elif not isinstance(value, list):
                        value = [value]
                
                # Handle link fields (need to wrap in list)
                if feishu_field == "所属项目" and value:
                    if isinstance(value, str):
                        value = [value]
            
            elif transform == "template" and mapping.get("template"):
                template = Template(mapping["template"])
                value = template.render(**spec_dict)
                field_map_snapshot[feishu_field] = spec_path or "template"
            
            # Apply default if no value
            if value is None and "default" in mapping:
                value = mapping["default"]
            
            # Only add if required or has value
            if value is not None or mapping.get("required", False):
                feishu_fields[feishu_field] = value
        
        return feishu_fields, field_map_snapshot

    def _get_nested_value(self, obj: Dict, path: str) -> Any:
        """Get a nested value from a dict using dot notation."""
        parts = path.split(".")
        for part in parts:
            if obj is None:
                return None
            if isinstance(obj, dict):
                obj = obj.get(part)
            else:
                return None
        return obj
