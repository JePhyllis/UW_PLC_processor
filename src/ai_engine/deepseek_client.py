"""
DeepSeek R1 API客户端
支持并行调用、错误处理和结果缓存
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Union
import aiohttp
import json
from dataclasses import dataclass
from loguru import logger
import openai
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue, Empty
import hashlib

from ..core.config import config


@dataclass
class AnalysisResult:
    """分析结果数据结构"""
    shard_id: str
    success: bool
    content: str
    error_message: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None
    processing_time: float = 0.0
    confidence_score: float = 0.0


class DeepSeekClient:
    """DeepSeek R1 API客户端"""
    
    def __init__(self):
        self.config = config.deepseek
        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.api_base
        )
        self.request_queue = Queue(maxsize=config.parallel.queue_size)
        self.results_cache: Dict[str, AnalysisResult] = {}
        self.rate_limiter = RateLimiter(self.config.max_concurrent_requests)
        
    def analyze_shard_batch(self, shards: List[Dict[str, Any]], analysis_type: str = "alarm") -> List[AnalysisResult]:
        """
        批量分析分片
        
        Args:
            shards: 分片列表
            analysis_type: 分析类型 (alarm, safety, logic)
            
        Returns:
            分析结果列表
        """
        logger.info(f"开始批量分析 {len(shards)} 个分片，类型: {analysis_type}")
        
        results = []
        
        # 使用线程池进行并行处理
        with ThreadPoolExecutor(max_workers=config.parallel.max_workers) as executor:
            # 提交所有任务
            future_to_shard = {}
            for shard in shards:
                future = executor.submit(self.analyze_single_shard, shard, analysis_type)
                future_to_shard[future] = shard
            
            # 收集结果
            for future in as_completed(future_to_shard, timeout=config.parallel.worker_timeout):
                shard = future_to_shard[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info(f"分片 {shard.get('shard_id', 'unknown')} 分析完成")
                except Exception as e:
                    logger.error(f"分片 {shard.get('shard_id', 'unknown')} 分析失败: {e}")
                    results.append(AnalysisResult(
                        shard_id=shard.get('shard_id', 'unknown'),
                        success=False,
                        content="",
                        error_message=str(e)
                    ))
        
        logger.info(f"批量分析完成，成功: {sum(1 for r in results if r.success)}, 失败: {sum(1 for r in results if not r.success)}")
        return results
    
    def analyze_single_shard(self, shard: Dict[str, Any], analysis_type: str) -> AnalysisResult:
        """
        分析单个分片
        
        Args:
            shard: 分片数据
            analysis_type: 分析类型
            
        Returns:
            分析结果
        """
        shard_id = shard.get('shard_id', 'unknown')
        start_time = time.time()
        
        # 检查缓存
        cache_key = self._generate_cache_key(shard, analysis_type)
        if cache_key in self.results_cache:
            logger.debug(f"使用缓存结果: {shard_id}")
            return self.results_cache[cache_key]
        
        try:
            # 限流
            with self.rate_limiter:
                # 构建提示词
                prompt = self._build_prompt(shard, analysis_type)
                
                # 调用API
                response = self._call_api(prompt)
                
                # 解析结果
                result = self._parse_response(shard_id, response, time.time() - start_time)
                
                # 缓存结果
                self.results_cache[cache_key] = result
                
                return result
                
        except Exception as e:
            logger.error(f"分析分片 {shard_id} 时发生错误: {e}")
            return AnalysisResult(
                shard_id=shard_id,
                success=False,
                content="",
                error_message=str(e),
                processing_time=time.time() - start_time
            )
    
    def _build_prompt(self, shard: Dict[str, Any], analysis_type: str) -> str:
        """构建分析提示词"""
        
        # 基础系统提示
        system_prompt = self._get_system_prompt(analysis_type)
        
        # 上下文信息
        context_info = shard.get('context_info', {})
        context_text = self._format_context(context_info)
        
        # 分片内容
        elements = shard.get('elements', [])
        content_text = self._format_elements(elements)
        
        # Few-shot示例
        examples = self._get_few_shot_examples(analysis_type)
        
        # 构建完整提示词
        prompt = f"""
{system_prompt}

## 上下文信息
{context_text}

## Few-Shot示例
{examples}

## 待分析的PLC代码
{content_text}

## 分析要求
请按照以下JSON格式输出分析结果：
{{
    "analysis_type": "{analysis_type}",
    "findings": [
        {{
            "type": "missing_alarm|existing_alarm|safety_issue|logic_error",
            "severity": "critical|high|medium|low",
            "location": "具体位置描述",
            "description": "详细描述",
            "recommendation": "改进建议",
            "confidence": 0.0-1.0
        }}
    ],
    "summary": "整体分析总结",
    "confidence_score": 0.0-1.0
}}
"""
        return prompt.strip()
    
    def _get_system_prompt(self, analysis_type: str) -> str:
        """获取系统提示词"""
        
        if analysis_type == "alarm":
            return """
你是一位资深的PLC程序工程师和工业自动化专家，专门负责分析PLC代码中的报警系统。

你的任务是：
1. 识别现有的报警配置和逻辑
2. 发现缺失的关键报警
3. 评估报警的合理性和完整性
4. 提供改进建议

重点关注：
- 安全相关的报警（急停、安全门、光栅等）
- 过程报警（温度、压力、速度超限等）
- 设备状态报警（电机故障、传感器故障等）
- 系统级报警（通信故障、I/O故障等）

分析时请考虑：
- 工业安全标准（如IEC 61508、ISO 13849）
- 报警管理最佳实践（ISA-18.2标准）
- 过程安全要求
- 设备保护需求
"""
        
        elif analysis_type == "safety":
            return """
你是一位功能安全专家，专门负责分析PLC代码的安全功能。

你的任务是：
1. 识别安全相关的逻辑和功能
2. 评估安全功能的完整性
3. 检查是否符合安全标准要求
4. 发现潜在的安全隐患

重点关注：
- 安全输入/输出的处理
- 安全联锁逻辑
- 故障检测和诊断
- 安全状态的维持
- 冗余和多样性设计
"""
        
        elif analysis_type == "logic":
            return """
你是一位PLC程序逻辑专家，专门负责分析程序逻辑的正确性。

你的任务是：
1. 检查程序逻辑的正确性
2. 识别潜在的逻辑错误
3. 评估程序的健壮性
4. 提供优化建议

重点关注：
- 条件判断的完整性
- 状态机逻辑
- 时序控制
- 异常处理
- 变量使用的一致性
"""
        
        return "你是一位PLC程序分析专家。"
    
    def _format_context(self, context_info: Dict[str, Any]) -> str:
        """格式化上下文信息"""
        if not context_info:
            return "无特定上下文信息"
        
        context_text = "相关依赖和上下文：\n"
        for name, info in context_info.items():
            if isinstance(info, dict):
                context_text += f"- {name} ({info.get('type', 'unknown')}): {info.get('summary', 'no description')}\n"
            else:
                context_text += f"- {name}: {str(info)}\n"
        
        return context_text
    
    def _format_elements(self, elements: List[Dict[str, Any]]) -> str:
        """格式化PLC元素内容"""
        if not elements:
            return "无代码内容"
        
        content_text = ""
        for element in elements:
            name = element.get('name', 'unnamed')
            element_type = element.get('type', 'unknown')
            content = element.get('content', '')
            
            content_text += f"\n### {element_type}: {name}\n"
            content_text += f"```\n{content}\n```\n"
        
        return content_text
    
    def _get_few_shot_examples(self, analysis_type: str) -> str:
        """获取Few-shot示例"""
        
        if analysis_type == "alarm":
            return """
示例1 - 缺失的温度报警：
输入：温度传感器读取但无超温报警
输出：
{
    "type": "missing_alarm",
    "severity": "high", 
    "location": "温度检测逻辑",
    "description": "检测到温度传感器TT_001读取，但缺少温度超限报警",
    "recommendation": "添加温度高报警（>80°C）和温度高高报警（>95°C）",
    "confidence": 0.9
}

示例2 - 现有的压力报警：
输入：压力传感器包含高压报警逻辑
输出：
{
    "type": "existing_alarm",
    "severity": "medium",
    "location": "压力控制回路",
    "description": "发现完整的压力报警配置，包括高压和低压报警",
    "recommendation": "报警配置合理，建议定期校验报警设定值",
    "confidence": 0.95
}
"""
        
        return "相关分析示例将根据具体情况提供。"
    
    def _call_api(self, prompt: str) -> Dict[str, Any]:
        """调用DeepSeek API"""
        
        for attempt in range(self.config.retry_times):
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    timeout=self.config.request_timeout
                )
                
                return {
                    "content": response.choices[0].message.content,
                    "usage": response.usage.model_dump() if response.usage else None
                }
                
            except Exception as e:
                logger.warning(f"API调用失败 (尝试 {attempt + 1}/{self.config.retry_times}): {e}")
                if attempt < self.config.retry_times - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise e
    
    def _parse_response(self, shard_id: str, response: Dict[str, Any], processing_time: float) -> AnalysisResult:
        """解析API响应"""
        
        content = response.get("content", "")
        usage = response.get("usage", {})
        
        # 尝试解析JSON结果
        try:
            # 提取JSON部分
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_content = content[json_start:json_end]
                parsed_result = json.loads(json_content)
                confidence_score = parsed_result.get('confidence_score', 0.5)
            else:
                # 如果无法解析JSON，使用原始内容
                confidence_score = 0.3
                
        except json.JSONDecodeError:
            confidence_score = 0.3
        
        return AnalysisResult(
            shard_id=shard_id,
            success=True,
            content=content,
            token_usage=usage,
            processing_time=processing_time,
            confidence_score=confidence_score
        )
    
    def _generate_cache_key(self, shard: Dict[str, Any], analysis_type: str) -> str:
        """生成缓存键"""
        # 使用分片内容和分析类型生成哈希
        content = json.dumps(shard, sort_keys=True) + analysis_type
        return hashlib.md5(content.encode()).hexdigest()


class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_requests: int):
        self.max_requests = max_requests
        self.current_requests = 0
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
    
    def __enter__(self):
        with self.condition:
            while self.current_requests >= self.max_requests:
                self.condition.wait()
            self.current_requests += 1
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        with self.condition:
            self.current_requests -= 1
            self.condition.notify()


# 全局客户端实例
deepseek_client = DeepSeekClient() 