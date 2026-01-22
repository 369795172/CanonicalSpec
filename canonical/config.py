"""
Configuration management for the Canonical system.

Loads configuration from environment variables and .env file.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class CanonicalConfig(BaseSettings):
    """Configuration settings for the Canonical system."""
    
    # Data directories
    data_dir: Path = Field(
        default=Path.home() / ".canonical",
        description="Base directory for all canonical data"
    )
    specs_dir: Optional[Path] = Field(None, description="Directory for specs")
    snapshots_dir: Optional[Path] = Field(None, description="Directory for snapshots")
    ledger_dir: Optional[Path] = Field(None, description="Directory for ledger")
    logs_dir: Optional[Path] = Field(None, description="Directory for logs")
    
    # LLM Configuration
    llm_api_key: Optional[str] = Field(None, description="LLM API key")
    llm_base_url: Optional[str] = Field(None, description="LLM base URL (for non-OpenAI providers)")
    llm_model: str = Field("gpt-4", description="LLM model to use")
    llm_temperature: float = Field(0.3, ge=0.0, le=2.0, description="LLM temperature")
    llm_max_tokens: int = Field(2000, gt=0, description="Max tokens for LLM response")
    
    # Feishu Configuration
    feishu_app_id: Optional[str] = Field(None, description="Feishu app ID")
    feishu_app_secret: Optional[str] = Field(None, description="Feishu app secret")
    feishu_base_token: Optional[str] = Field(None, description="Feishu bitable app token")
    feishu_table_id: Optional[str] = Field(None, description="Feishu bitable table ID")
    
    # Mapping Configuration
    mapping_config_path: Optional[Path] = Field(None, description="Path to mapping config YAML")
    
    # Project defaults
    default_project_record_id: Optional[str] = Field(None, description="Default project record ID")
    default_mentor_user_id: Optional[str] = Field(None, description="Default mentor user ID")
    default_intern_user_id: Optional[str] = Field(None, description="Default intern user ID")
    
    # AI Builder Space Configuration
    ai_builder_token: Optional[str] = Field(None, description="AI Builder Space API token")
    ai_builder_base_url: str = Field(
        "https://space.ai-builders.com/backend/v1",
        description="AI Builder Space API base URL"
    )

    model_config = {
        "env_prefix": "CANONICAL_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",  # Ignore extra fields from env
    }

    def model_post_init(self, __context) -> None:
        """Initialize derived paths after loading config."""
        # Set derived paths if not explicitly configured
        if self.specs_dir is None:
            self.specs_dir = self.data_dir / "specs"
        if self.snapshots_dir is None:
            self.snapshots_dir = self.data_dir / "snapshots"
        if self.ledger_dir is None:
            self.ledger_dir = self.data_dir / "ledger"
        if self.logs_dir is None:
            self.logs_dir = self.data_dir / "logs"
        if self.mapping_config_path is None:
            self.mapping_config_path = self.data_dir / "config" / "mapping.yaml"

    def ensure_directories(self) -> None:
        """Create all necessary directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.specs_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create config directory for mapping file
        config_dir = self.data_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)


# Global config instance - loaded from environment
config = CanonicalConfig()
