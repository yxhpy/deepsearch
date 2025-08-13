"""
配置管理器 - 处理配置加载和提供商初始化
"""
import yaml
import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain.chat_models.base import BaseChatModel
from langchain.embeddings.base import Embeddings


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        load_dotenv()  # 加载.env文件
    
    def _load_config(self) -> Dict[str, Any]:
        """加载YAML配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件 {self.config_path} 不存在")
        except yaml.YAMLError as e:
            raise ValueError(f"配置文件解析错误: {e}")
    
    def get_llm(self) -> BaseChatModel:
        """获取LLM实例"""
        llm_config = self.config["providers"]["llm"]
        provider = llm_config["provider"]
        
        if provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=llm_config["openai"]["chat_model"],
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL") or None
            )
        
        elif provider == "azure":
            from langchain_openai import AzureChatOpenAI
            return AzureChatOpenAI(
                deployment_name=llm_config["azure"]["chat_deployment"],
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION")
            )
        
        elif provider == "ollama":
            from langchain_community.chat_models import ChatOllama
            return ChatOllama(
                model=llm_config["ollama"]["chat_model"],
                base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434")
            )
        
        else:
            raise ValueError(f"不支持的LLM提供商: {provider}")
    
    def get_embeddings(self) -> Embeddings:
        """获取Embeddings实例"""
        embed_config = self.config["providers"]["embedding"]
        provider = embed_config["provider"]
        
        if provider == "openai":
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(
                model=embed_config["openai"]["embed_model"],
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL") or None
            )
        
        elif provider == "azure":
            from langchain_openai import AzureOpenAIEmbeddings
            return AzureOpenAIEmbeddings(
                deployment=embed_config["azure"]["embed_deployment"],
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION")
            )
        
        elif provider == "ollama":
            from langchain_community.embeddings import OllamaEmbeddings
            return OllamaEmbeddings(
                model=embed_config["ollama"]["embed_model"],
                base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434")
            )
        
        elif provider == "dashscope":
            from langchain_community.embeddings import DashScopeEmbeddings
            return DashScopeEmbeddings(
                model=embed_config["dashscope"]["embed_model"],
                dashscope_api_key=os.getenv("DASHSCOPE_API_KEY")
            )
        
        else:
            raise ValueError(f"不支持的Embedding提供商: {provider}")
    
    def get_search_config(self) -> Dict[str, Any]:
        """获取搜索配置"""
        return self.config["providers"]["search"]
    
    def get_runtime_config(self) -> Dict[str, Any]:
        """获取运行时配置"""
        return self.config.get("runtime", {})
    
    def get_logic_config(self) -> Dict[str, Any]:
        """获取逻辑配置"""
        return self.config.get("logic", {})
    
    def get_scoring_weights(self) -> Dict[str, float]:
        """获取评分权重"""
        return self.config.get("scoring_weights", {})
    
    def get_export_config(self) -> Dict[str, Any]:
        """获取导出配置"""
        return self.config.get("export", {})