"""
Feishu Publisher - Adapter for publishing specs to Feishu (Lark Base).

Implements the publish contract from 04_feishu_publish_contract.md.

Also provides FeishuReader for reading doc/wiki content.
"""

import json
import re
import yaml
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from jinja2 import Template
import requests

from canonical.models.spec import CanonicalSpec, FeatureStatus
from canonical.store.ledger import Ledger, LedgerRecord, LedgerStatus
from canonical.config import config


@dataclass
class FeishuReadError:
    """Unified error structure for read failures."""

    endpoint: str
    code: int
    msg: str
    request_id: Optional[str] = None


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
                    "fixed_value": "高",
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
                    "required": True,
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

    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[FeishuReadError]]:
        """
        Execute request with timeout/retry and return (data, error).
        On success: (data, None). On failure: (None, FeishuReadError).
        """
        timeout = getattr(config, "feishu_timeout", 30) or 30
        retry_count = getattr(config, "feishu_retry", 3) or 0
        last_error = None

        for attempt in range(retry_count + 1):
            try:
                resp = requests.request(
                    method,
                    url,
                    headers=self._headers(),
                    timeout=timeout,
                    **kwargs,
                )
                data = resp.json() if resp.content else {}
                request_id = resp.headers.get("X-Request-Id") or data.get("request_id")

                if resp.status_code == 429:
                    last_error = FeishuReadError(
                        endpoint=url,
                        code=429,
                        msg=data.get("msg", "Rate limited"),
                        request_id=request_id,
                    )
                    continue

                if resp.status_code >= 400:
                    last_error = FeishuReadError(
                        endpoint=url,
                        code=data.get("code", resp.status_code),
                        msg=data.get("msg", resp.reason or f"HTTP {resp.status_code}"),
                        request_id=request_id,
                    )
                    return (None, last_error)

                if data.get("code", 0) != 0:
                    last_error = FeishuReadError(
                        endpoint=url,
                        code=data.get("code", -1),
                        msg=data.get("msg", "Unknown API error"),
                        request_id=request_id,
                    )
                    return (None, last_error)

                return (data, None)

            except requests.exceptions.Timeout as e:
                last_error = FeishuReadError(
                    endpoint=url,
                    code=-1,
                    msg=f"Timeout: {str(e)}",
                )
            except requests.exceptions.RequestException as e:
                last_error = FeishuReadError(
                    endpoint=url,
                    code=-1,
                    msg=str(e),
                )
                break

        return (None, last_error)

    def get_doc_metadata(self, document_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[FeishuReadError]]:
        """Get document metadata (title, etc.) for docx document."""
        url = f"{self.BASE_URL}/docx/v1/documents/{document_id}"
        data, err = self._request("GET", url)
        if err:
            return (None, err)
        return (data.get("data"), None)

    def get_doc_raw_content(self, document_id: str) -> Tuple[Optional[str], Optional[FeishuReadError]]:
        """Get raw plain text content of docx document."""
        url = f"{self.BASE_URL}/docx/v1/documents/{document_id}/raw_content"
        data, err = self._request("GET", url)
        if err:
            return (None, err)
        content = (data or {}).get("data", {}).get("content", "")
        return (content or "", None)

    def get_wiki_node(self, space_id: str, node_token: str) -> Tuple[Optional[Dict[str, Any]], Optional[FeishuReadError]]:
        """Get wiki node info by space_id + node_token (space_id must be numeric)."""
        url = f"{self.BASE_URL}/wiki/v2/spaces/{space_id}/nodes/{node_token}"
        data, err = self._request("GET", url)
        if err:
            return (None, err)
        return (data.get("data", {}).get("node"), None)

    def get_wiki_node_by_token(self, token: str) -> Tuple[Optional[Dict[str, Any]], Optional[FeishuReadError]]:
        """Get wiki node info by token only (for single-token wiki URLs)."""
        url = f"{self.BASE_URL}/wiki/v2/spaces/get_node?token={token}"
        data, err = self._request("GET", url)
        if err:
            return (None, err)
        return (data.get("data", {}).get("node"), None)


def resolve_url_to_token(url: str) -> Tuple[Optional[str], Optional[str], Optional[Tuple[str, str]]]:
    """
    Parse Feishu URL to extract document/wiki tokens.

    Returns:
        (doc_type, token, wiki_ids) where:
        - doc_type: "docx" | "docs" | "wiki"
        - token: document_id or doc_token or node_token
        - wiki_ids: (space_id, node_token) only when doc_type is "wiki"
    """
    if not url or not isinstance(url, str):
        return (None, None, None)

    url = url.strip()

    # docx: https://xxx.feishu.cn/docx/XXXX
    m = re.search(r"feishu\.cn/docx/([A-Za-z0-9]+)", url)
    if m:
        return ("docx", m.group(1), None)

    # docs (old): https://xxx.feishu.cn/docs/XXXX
    m = re.search(r"feishu\.cn/docs/([A-Za-z0-9]+)", url)
    if m:
        return ("docs", m.group(1), None)

    # wiki: https://xxx.feishu.cn/wiki/XXXX or wiki/space_id/node_token
    m = re.search(r"feishu\.cn/wiki/([A-Za-z0-9]+)(?:/([A-Za-z0-9]+))?", url)
    if m:
        space_id = m.group(1)
        node_token = m.group(2) or m.group(1)
        if m.group(2):
            return ("wiki", node_token, (space_id, node_token))
        return ("wiki", space_id, (space_id, space_id))

    return (None, None, None)


def normalize_doc_content(raw: str) -> Dict[str, Any]:
    """Extract plain_text and blocks from raw content."""
    plain_text = (raw or "").strip()
    blocks = []
    for para in plain_text.split("\n\n"):
        para = para.strip()
        if para:
            blocks.append({"type": "paragraph", "text": para})
    return {"plain_text": plain_text, "blocks": blocks}


class FeishuReader:
    """Reader for Feishu doc/wiki content. Handles read + normalize only."""

    def __init__(self, client: Optional[FeishuClient] = None):
        self._client = client

    @property
    def client(self) -> FeishuClient:
        if self._client is None:
            self._client = FeishuClient()
        return self._client

    def read(
        self,
        url: Optional[str] = None,
        document_token: Optional[str] = None,
        wiki_token: Optional[str] = None,
        wiki_space_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Read Feishu document content.

        Args:
            url: Feishu doc/wiki URL (preferred)
            document_token: Direct document_id (docx) or doc_token (docs)
            wiki_token: Wiki node_token (requires wiki_space_id)
            wiki_space_id: Wiki space_id (required when using wiki_token)

        Returns:
            {
                "title": str,
                "plain_text": str,
                "blocks": list,
                "source_url": str,
                "debug": dict | None (present on error)
            }
        """
        source_url = url or ""
        debug = None

        # Resolve input to document_id
        doc_id = None
        if url:
            doc_type, token, wiki_ids = resolve_url_to_token(url)
            if doc_type == "docx":
                doc_id = token
            elif doc_type == "docs":
                doc_id = token
            elif doc_type == "wiki" and wiki_ids:
                space_id, node_token = wiki_ids
                if space_id == node_token or not space_id.isdigit():
                    node, err = self.client.get_wiki_node_by_token(node_token)
                else:
                    node, err = self.client.get_wiki_node(space_id, node_token)
                if err:
                    return {
                        "title": "",
                        "plain_text": "",
                        "blocks": [],
                        "source_url": source_url,
                        "debug": {
                            "endpoint": err.endpoint,
                            "code": err.code,
                            "msg": err.msg,
                            "request_id": err.request_id,
                        },
                    }
                if node:
                    obj_type = node.get("obj_type")
                    obj_token = node.get("obj_token")
                    if obj_token and obj_type in ("doc", "docx"):
                        doc_id = obj_token
                    else:
                        return {
                            "title": node.get("title", ""),
                            "plain_text": "",
                            "blocks": [],
                            "source_url": source_url,
                            "debug": {
                                "msg": f"Wiki node obj_type={obj_type} not supported (doc/docx), obj_token={obj_token}",
                            },
                        }
        elif document_token:
            doc_id = document_token
        elif wiki_token and wiki_space_id:
            node, err = self.client.get_wiki_node(wiki_space_id, wiki_token)
            if err:
                return {
                    "title": "",
                    "plain_text": "",
                    "blocks": [],
                    "source_url": source_url,
                    "debug": {
                        "endpoint": err.endpoint,
                        "code": err.code,
                        "msg": err.msg,
                        "request_id": err.request_id,
                    },
                }
            if node:
                obj_type = node.get("obj_type")
                obj_token = node.get("obj_token")
                if obj_token and obj_type in ("doc", "docx"):
                    doc_id = obj_token
                else:
                    return {
                        "title": node.get("title", ""),
                        "plain_text": "",
                        "blocks": [],
                        "source_url": source_url,
                        "debug": {"msg": f"Wiki node obj_type={obj_type} not supported (doc/docx)"},
                    }

        if not doc_id:
            return {
                "title": "",
                "plain_text": "",
                "blocks": [],
                "source_url": source_url,
                "debug": {"msg": "No url, document_token, or valid wiki_token+wiki_space_id provided"},
            }

        # Get metadata (title)
        meta, err = self.client.get_doc_metadata(doc_id)
        if err:
            return {
                "title": "",
                "plain_text": "",
                "blocks": [],
                "source_url": source_url,
                "debug": {
                    "endpoint": err.endpoint,
                    "code": err.code,
                    "msg": err.msg,
                    "request_id": err.request_id,
                },
            }
        title = (meta or {}).get("title", "")

        # Get raw content
        raw, err = self.client.get_doc_raw_content(doc_id)
        if err:
            return {
                "title": title,
                "plain_text": "",
                "blocks": [],
                "source_url": source_url,
                "debug": {
                    "endpoint": err.endpoint,
                    "code": err.code,
                    "msg": err.msg,
                    "request_id": err.request_id,
                },
            }

        normalized = normalize_doc_content(raw or "")
        return {
            "title": title,
            "plain_text": normalized["plain_text"],
            "blocks": normalized["blocks"],
            "source_url": source_url or f"https://example.feishu.cn/docx/{doc_id}",
        }


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
        
        # Validate required fields
        if not spec.project_context_ref or not spec.project_context_ref.project_record_id:
            raise ValueError("project_context_ref.project_record_id 是发布必填字段")
        
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
