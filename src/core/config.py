"""
配置管理模块
负责加载配置文件和环境变量
"""

import os
import yaml
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from pathlib import Path


class DeepSeekConfig(BaseModel):
    """DeepSeek R1配置"""
    api_base: str = Field(default="https://api.deepseek.com/v1")
    api_key: str = Field(default="")
    model: str = Field(default="deepseek-r1")
    max_tokens: int = Field(default=32000)
    temperature: float = Field(default=0.1)
    max_concurrent_requests: int = Field(default=20)
    request_timeout: int = Field(default=300)
    retry_times: int = Field(default=3)
    retry_delay: int = Field(default=2)


class XMLProcessingConfig(BaseModel):
    """XML处理配置"""
    max_shard_lines: int = Field(default=1500)
    min_shard_lines: int = Field(default=800)
    overlap_lines: int = Field(default=100)
    target_shard_count: int = Field(default=150)
    chunk_size: int = Field(default=1024)
    encoding: str = Field(default="utf-8")


class ParallelConfig(BaseModel):
    """并行处理配置"""
    max_workers: int = Field(default=20)
    batch_size: int = Field(default=16)
    queue_size: int = Field(default=500)
    worker_timeout: int = Field(default=600)
    result_timeout: int = Field(default=300)


class KnowledgeGraphConfig(BaseModel):
    """知识图谱配置"""
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="")
    max_connections: int = Field(default=50)
    connection_timeout: int = Field(default=30)


class AnalysisConfig(BaseModel):
    """分析配置"""
    few_shot_examples: int = Field(default=5)
    confidence_threshold: float = Field(default=0.7)
    max_analysis_depth: int = Field(default=3)
    context_window_size: int = Field(default=2000)


class AppConfig(BaseModel):
    """应用主配置"""
    name: str = Field(default="PLC报警系统分析器")
    version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")


class Config:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config.yaml"
        self._config_data: Dict[str, Any] = {}
        self.load_config()
        
        # 初始化各个配置模块
        self.app = AppConfig(**self._config_data.get("app", {}))
        self.deepseek = DeepSeekConfig(**self._resolve_env_vars(self._config_data.get("deepseek", {})))
        self.xml_processing = XMLProcessingConfig(**self._config_data.get("xml_processing", {}))
        self.parallel = ParallelConfig(**self._config_data.get("parallel", {}))
        self.knowledge_graph = KnowledgeGraphConfig(**self._resolve_env_vars(self._config_data.get("knowledge_graph", {})))
        self.analysis = AnalysisConfig(**self._config_data.get("analysis", {}))
    
    def load_config(self):
        """加载配置文件"""
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    self._config_data = yaml.safe_load(f) or {}
            else:
                print(f"Warning: Config file {self.config_path} not found, using defaults")
                self._config_data = {}
        except Exception as e:
            print(f"Error loading config: {e}")
            self._config_data = {}
    
    def _resolve_env_vars(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """解析环境变量"""
        resolved = {}
        for key, value in config_dict.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                resolved[key] = os.getenv(env_var, "")
            else:
                resolved[key] = value
        return resolved
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self._config_data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def validate(self) -> bool:
        """验证配置完整性"""
        errors = []
        
        # 检查必要的API密钥
        if not self.deepseek.api_key:
            errors.append("DEEPSEEK_API_KEY environment variable is required")
        
        # 检查配置合理性
        if self.xml_processing.max_shard_lines <= self.xml_processing.min_shard_lines:
            errors.append("max_shard_lines must be greater than min_shard_lines")
        
        if self.parallel.max_workers <= 0:
            errors.append("max_workers must be positive")
        
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        return True


# 全局配置实例
config = Config() 