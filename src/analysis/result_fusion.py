"""
结果融合模块
将多个分片的分析结果合并并生成综合报告
"""

import json
import statistics
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
from datetime import datetime
import networkx as nx
from loguru import logger

from ..ai_engine.deepseek_client import AnalysisResult


@dataclass
class Finding:
    """分析发现"""
    type: str  # missing_alarm, existing_alarm, safety_issue, logic_error
    severity: str  # critical, high, medium, low
    location: str
    description: str
    recommendation: str
    confidence: float
    source_shards: List[str]  # 来源分片
    frequency: int = 1  # 出现频次


@dataclass
class FusedResult:
    """融合后的分析结果"""
    analysis_type: str
    findings: List[Finding]
    summary: str
    overall_confidence: float
    statistics: Dict[str, Any]
    processing_info: Dict[str, Any]
    timestamp: str


class ResultFusion:
    """结果融合器"""
    
    def __init__(self):
        self.confidence_threshold = 0.5
        self.similarity_threshold = 0.8
        
    def fuse_analysis_results(self, results: List[AnalysisResult], analysis_type: str) -> FusedResult:
        """
        融合分析结果
        
        Args:
            results: 分析结果列表
            analysis_type: 分析类型
            
        Returns:
            融合后的结果
        """
        logger.info(f"开始融合 {len(results)} 个分析结果")
        
        # 过滤成功的结果
        successful_results = [r for r in results if r.success]
        logger.info(f"成功结果: {len(successful_results)} / {len(results)}")
        
        if not successful_results:
            return self._create_empty_result(analysis_type, "所有分析都失败了")
        
        # 解析所有发现
        all_findings = self._extract_findings(successful_results)
        
        # 去重和合并相似发现
        deduplicated_findings = self._deduplicate_findings(all_findings)
        
        # 按重要性排序
        sorted_findings = self._sort_findings(deduplicated_findings)
        
        # 生成统计信息
        statistics = self._generate_statistics(successful_results, sorted_findings)
        
        # 生成综合摘要
        summary = self._generate_summary(sorted_findings, statistics)
        
        # 计算整体置信度
        overall_confidence = self._calculate_overall_confidence(successful_results, sorted_findings)
        
        # 生成处理信息
        processing_info = self._generate_processing_info(results)
        
        return FusedResult(
            analysis_type=analysis_type,
            findings=sorted_findings,
            summary=summary,
            overall_confidence=overall_confidence,
            statistics=statistics,
            processing_info=processing_info,
            timestamp=datetime.now().isoformat()
        )
    
    def _extract_findings(self, results: List[AnalysisResult]) -> List[Finding]:
        """从分析结果中提取发现"""
        all_findings = []
        
        for result in results:
            try:
                # 尝试解析JSON内容
                content = result.content
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_content = content[json_start:json_end]
                    parsed_result = json.loads(json_content)
                    
                    findings = parsed_result.get('findings', [])
                    for finding_data in findings:
                        finding = Finding(
                            type=finding_data.get('type', 'unknown'),
                            severity=finding_data.get('severity', 'low'),
                            location=finding_data.get('location', '未知位置'),
                            description=finding_data.get('description', ''),
                            recommendation=finding_data.get('recommendation', ''),
                            confidence=finding_data.get('confidence', 0.5),
                            source_shards=[result.shard_id]
                        )
                        all_findings.append(finding)
                        
            except json.JSONDecodeError:
                # 如果无法解析JSON，尝试从文本中提取关键信息
                logger.warning(f"无法解析分片 {result.shard_id} 的JSON结果，尝试文本解析")
                text_findings = self._extract_findings_from_text(result)
                all_findings.extend(text_findings)
            except Exception as e:
                logger.error(f"提取分片 {result.shard_id} 的发现时出错: {e}")
                continue
        
        logger.info(f"提取到 {len(all_findings)} 个原始发现")
        return all_findings
    
    def _extract_findings_from_text(self, result: AnalysisResult) -> List[Finding]:
        """从文本内容中提取发现"""
        findings = []
        
        # 简单的关键词匹配
        content = result.content.lower()
        
        # 检测缺失报警
        if any(keyword in content for keyword in ['缺失', 'missing', '没有', '缺少']):
            if any(keyword in content for keyword in ['报警', 'alarm', '警报']):
                finding = Finding(
                    type='missing_alarm',
                    severity='medium',
                    location=f"分片 {result.shard_id}",
                    description="检测到可能的缺失报警",
                    recommendation="需要进一步分析具体的报警需求",
                    confidence=0.6,
                    source_shards=[result.shard_id]
                )
                findings.append(finding)
        
        # 检测安全问题
        if any(keyword in content for keyword in ['安全', 'safety', '危险', 'hazard']):
            finding = Finding(
                type='safety_issue',
                severity='high',
                location=f"分片 {result.shard_id}",
                description="检测到可能的安全相关问题",
                recommendation="需要详细的安全分析",
                confidence=0.5,
                source_shards=[result.shard_id]
            )
            findings.append(finding)
        
        return findings
    
    def _deduplicate_findings(self, findings: List[Finding]) -> List[Finding]:
        """去重和合并相似发现"""
        if not findings:
            return []
        
        # 按类型和严重程度分组
        groups = defaultdict(list)
        
        for finding in findings:
            key = (finding.type, finding.severity)
            groups[key].append(finding)
        
        deduplicated = []
        
        for group_findings in groups.values():
            # 对每组内的发现进行相似性检查
            merged_findings = self._merge_similar_findings(group_findings)
            deduplicated.extend(merged_findings)
        
        logger.info(f"去重后剩余 {len(deduplicated)} 个发现")
        return deduplicated
    
    def _merge_similar_findings(self, findings: List[Finding]) -> List[Finding]:
        """合并相似的发现"""
        if len(findings) <= 1:
            return findings
        
        merged = []
        used_indices = set()
        
        for i, finding1 in enumerate(findings):
            if i in used_indices:
                continue
                
            similar_findings = [finding1]
            
            for j, finding2 in enumerate(findings[i+1:], i+1):
                if j in used_indices:
                    continue
                    
                similarity = self._calculate_similarity(finding1, finding2)
                if similarity > self.similarity_threshold:
                    similar_findings.append(finding2)
                    used_indices.add(j)
            
            # 合并相似发现
            merged_finding = self._merge_findings(similar_findings)
            merged.append(merged_finding)
            used_indices.add(i)
        
        return merged
    
    def _calculate_similarity(self, finding1: Finding, finding2: Finding) -> float:
        """计算两个发现的相似性"""
        # 简单的相似性计算
        score = 0.0
        
        # 类型匹配
        if finding1.type == finding2.type:
            score += 0.4
        
        # 严重程度匹配
        if finding1.severity == finding2.severity:
            score += 0.2
        
        # 描述相似性（简单的关键词匹配）
        desc1_words = set(finding1.description.lower().split())
        desc2_words = set(finding2.description.lower().split())
        
        if desc1_words and desc2_words:
            common_words = desc1_words & desc2_words
            all_words = desc1_words | desc2_words
            desc_similarity = len(common_words) / len(all_words)
            score += 0.4 * desc_similarity
        
        return score
    
    def _merge_findings(self, findings: List[Finding]) -> Finding:
        """合并多个发现为一个"""
        if len(findings) == 1:
            return findings[0]
        
        # 取第一个作为基础
        base = findings[0]
        
        # 合并源分片
        all_source_shards = []
        for finding in findings:
            all_source_shards.extend(finding.source_shards)
        
        # 计算平均置信度
        avg_confidence = statistics.mean(f.confidence for f in findings)
        
        # 合并描述
        descriptions = [f.description for f in findings if f.description]
        merged_description = base.description
        if len(descriptions) > 1:
            merged_description += f" (在 {len(descriptions)} 个位置发现)"
        
        return Finding(
            type=base.type,
            severity=base.severity,
            location=base.location,
            description=merged_description,
            recommendation=base.recommendation,
            confidence=avg_confidence,
            source_shards=list(set(all_source_shards)),
            frequency=len(findings)
        )
    
    def _sort_findings(self, findings: List[Finding]) -> List[Finding]:
        """按重要性排序发现"""
        severity_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        
        return sorted(findings, key=lambda f: (
            severity_order.get(f.severity, 0),
            f.confidence,
            f.frequency
        ), reverse=True)
    
    def _generate_statistics(self, results: List[AnalysisResult], findings: List[Finding]) -> Dict[str, Any]:
        """生成统计信息"""
        # 基础统计
        total_shards = len(results)
        successful_shards = len([r for r in results if r.success])
        success_rate = successful_shards / total_shards if total_shards > 0 else 0
        
        # 发现统计
        finding_types = Counter(f.type for f in findings)
        severity_counts = Counter(f.severity for f in findings)
        
        # 置信度统计
        confidences = [f.confidence for f in findings]
        avg_confidence = statistics.mean(confidences) if confidences else 0
        
        # 处理时间统计
        processing_times = [r.processing_time for r in results if r.success]
        avg_processing_time = statistics.mean(processing_times) if processing_times else 0
        total_processing_time = sum(processing_times)
        
        # Token使用统计
        total_tokens = 0
        for result in results:
            if result.token_usage:
                total_tokens += result.token_usage.get('total_tokens', 0)
        
        return {
            'total_shards': total_shards,
            'successful_shards': successful_shards,
            'success_rate': success_rate,
            'total_findings': len(findings),
            'finding_types': dict(finding_types),
            'severity_counts': dict(severity_counts),
            'average_confidence': avg_confidence,
            'total_processing_time': total_processing_time,
            'average_processing_time': avg_processing_time,
            'total_tokens_used': total_tokens
        }
    
    def _generate_summary(self, findings: List[Finding], statistics: Dict[str, Any]) -> str:
        """生成综合摘要"""
        if not findings:
            return "本次分析未发现显著问题。"
        
        summary_parts = []
        
        # 总体统计
        total_findings = len(findings)
        critical_count = len([f for f in findings if f.severity == 'critical'])
        high_count = len([f for f in findings if f.severity == 'high'])
        
        summary_parts.append(f"分析发现 {total_findings} 个问题")
        
        if critical_count > 0:
            summary_parts.append(f"其中 {critical_count} 个严重问题")
        if high_count > 0:
            summary_parts.append(f"{high_count} 个高优先级问题")
        
        # 主要问题类型
        finding_types = statistics['finding_types']
        if finding_types:
            main_type = max(finding_types.items(), key=lambda x: x[1])
            if main_type[1] > 1:
                type_names = {
                    'missing_alarm': '缺失报警',
                    'existing_alarm': '现有报警',
                    'safety_issue': '安全问题',
                    'logic_error': '逻辑错误'
                }
                summary_parts.append(f"主要问题类型为{type_names.get(main_type[0], main_type[0])}({main_type[1]}个)")
        
        # 关键建议
        critical_findings = [f for f in findings if f.severity in ['critical', 'high']]
        if critical_findings:
            summary_parts.append("建议优先处理高优先级问题")
        
        return "。".join(summary_parts) + "。"
    
    def _calculate_overall_confidence(self, results: List[AnalysisResult], findings: List[Finding]) -> float:
        """计算整体置信度"""
        # 基于多个因素计算置信度
        factors = []
        
        # 成功率因子
        success_rate = len([r for r in results if r.success]) / len(results) if results else 0
        factors.append(success_rate)
        
        # 发现置信度因子
        if findings:
            avg_finding_confidence = statistics.mean(f.confidence for f in findings)
            factors.append(avg_finding_confidence)
        
        # 结果一致性因子（基于重复发现的频次）
        if findings:
            frequencies = [f.frequency for f in findings]
            consistency_factor = min(1.0, statistics.mean(frequencies) / 3.0)  # 标准化到0-1
            factors.append(consistency_factor)
        
        # 计算加权平均
        weights = [0.4, 0.4, 0.2]  # 成功率、发现置信度、一致性
        
        if len(factors) < len(weights):
            weights = weights[:len(factors)]
            weights = [w / sum(weights) for w in weights]  # 重新标准化
        
        overall_confidence = sum(f * w for f, w in zip(factors, weights))
        return min(1.0, max(0.0, overall_confidence))
    
    def _generate_processing_info(self, results: List[AnalysisResult]) -> Dict[str, Any]:
        """生成处理信息"""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        info = {
            'total_results': len(results),
            'successful_results': len(successful),
            'failed_results': len(failed),
            'failed_shard_ids': [r.shard_id for r in failed],
            'error_summary': {}
        }
        
        # 统计错误类型
        if failed:
            error_types = Counter()
            for result in failed:
                if result.error_message:
                    # 简单的错误分类
                    error_msg = result.error_message.lower()
                    if 'timeout' in error_msg:
                        error_types['timeout'] += 1
                    elif 'rate limit' in error_msg:
                        error_types['rate_limit'] += 1
                    elif 'api' in error_msg:
                        error_types['api_error'] += 1
                    else:
                        error_types['other'] += 1
            
            info['error_summary'] = dict(error_types)
        
        return info
    
    def _create_empty_result(self, analysis_type: str, reason: str) -> FusedResult:
        """创建空的结果"""
        return FusedResult(
            analysis_type=analysis_type,
            findings=[],
            summary=f"分析未能完成: {reason}",
            overall_confidence=0.0,
            statistics={},
            processing_info={'error': reason},
            timestamp=datetime.now().isoformat()
        )
    
    def export_results_to_json(self, result: FusedResult, output_path: str):
        """导出结果到JSON文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"结果已导出到 {output_path}")
    
    def generate_html_report(self, result: FusedResult, output_path: str):
        """生成HTML报告"""
        html_content = self._build_html_report(result)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"HTML报告已生成: {output_path}")
    
    def _build_html_report(self, result: FusedResult) -> str:
        """构建HTML报告"""
        findings_html = ""
        
        for i, finding in enumerate(result.findings, 1):
            severity_class = f"severity-{finding.severity}"
            findings_html += f"""
            <div class="finding {severity_class}">
                <h3>发现 #{i}: {finding.type}</h3>
                <div class="finding-details">
                    <p><strong>严重程度:</strong> <span class="severity">{finding.severity}</span></p>
                    <p><strong>位置:</strong> {finding.location}</p>
                    <p><strong>描述:</strong> {finding.description}</p>
                    <p><strong>建议:</strong> {finding.recommendation}</p>
                    <p><strong>置信度:</strong> {finding.confidence:.2f}</p>
                    <p><strong>出现频次:</strong> {finding.frequency}</p>
                </div>
            </div>
            """
        
        statistics_html = ""
        for key, value in result.statistics.items():
            statistics_html += f"<tr><td>{key}</td><td>{value}</td></tr>"
        
        html_template = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>PLC报警系统分析报告</title>
            <style>
                body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; }}
                .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 5px; }}
                .summary {{ background: #ecf0f1; padding: 15px; margin: 20px 0; border-radius: 5px; }}
                .finding {{ margin: 15px 0; padding: 15px; border-radius: 5px; border-left: 5px solid; }}
                .severity-critical {{ background: #ffebee; border-color: #f44336; }}
                .severity-high {{ background: #fff3e0; border-color: #ff9800; }}
                .severity-medium {{ background: #f3e5f5; border-color: #9c27b0; }}
                .severity-low {{ background: #e8f5e8; border-color: #4caf50; }}
                .statistics table {{ width: 100%; border-collapse: collapse; }}
                .statistics th, .statistics td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                .confidence {{ font-weight: bold; color: #2196f3; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>PLC报警系统分析报告</h1>
                <p>分析类型: {result.analysis_type} | 生成时间: {result.timestamp}</p>
                <p>整体置信度: <span class="confidence">{result.overall_confidence:.2f}</span></p>
            </div>
            
            <div class="summary">
                <h2>分析摘要</h2>
                <p>{result.summary}</p>
            </div>
            
            <div class="findings">
                <h2>详细发现 ({len(result.findings)}个)</h2>
                {findings_html}
            </div>
            
            <div class="statistics">
                <h2>统计信息</h2>
                <table>
                    <thead>
                        <tr><th>指标</th><th>值</th></tr>
                    </thead>
                    <tbody>
                        {statistics_html}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """
        
        return html_template


# 全局融合器实例
result_fusion = ResultFusion() 