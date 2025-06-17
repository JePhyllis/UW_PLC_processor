"""
XML解析器模块
负责解析PLC XML文件并进行智能分片处理
"""

import re
import os
import json
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, asdict
from pathlib import Path
from lxml import etree
import xml.etree.ElementTree as ET
from loguru import logger

from ..core.config import config


@dataclass
class PLCElement:
    """PLC元素数据结构"""
    name: str
    type: str  # GlobalVariable, DataType, FunctionBlock, Program, etc.
    content: str
    dependencies: Set[str]
    line_start: int
    line_end: int
    size_estimate: int  # Token估算


@dataclass
class XMLShard:
    """XML分片数据结构"""
    shard_id: str
    shard_type: str  # 'data_definition' or 'program_logic'
    elements: List[PLCElement]
    context_info: Dict[str, str]  # 上下文信息
    dependencies: Set[str]  # 依赖的其他分片
    line_start: int
    line_end: int
    total_lines: int
    token_estimate: int


class PLCXMLParser:
    """PLC XML解析器"""
    
    def __init__(self):
        self.config = config.xml_processing
        self.global_variables: Dict[str, PLCElement] = {}
        self.data_types: Dict[str, PLCElement] = {}
        self.function_blocks: Dict[str, PLCElement] = {}
        self.programs: Dict[str, PLCElement] = {}
        self.dependencies: Dict[str, Set[str]] = {}
        
    def parse_file(self, file_path: str) -> Tuple[List[XMLShard], Dict[str, str]]:
        """
        解析XML文件并返回分片
        
        Args:
            file_path: XML文件路径
            
        Returns:
            (分片列表, 全局上下文)
        """
        logger.info(f"开始解析XML文件: {file_path}")
        
        # 读取文件
        with open(file_path, 'r', encoding=self.config.encoding) as f:
            content = f.read()
        
        # 解析XML结构
        root = self._parse_xml_structure(content)
        
        # 提取PLC元素
        self._extract_plc_elements(root, content)
        
        # 分析依赖关系
        self._analyze_dependencies()
        
        # 生成分片
        shards = self._generate_shards()
        
        # 生成全局上下文
        global_context = self._generate_global_context()
        
        logger.info(f"解析完成，生成 {len(shards)} 个分片")
        return shards, global_context
    
    def _parse_xml_structure(self, content: str) -> ET.Element:
        """解析XML结构"""
        try:
            # 使用lxml解析，支持大文件
            parser = etree.XMLParser(strip_cdata=False, recover=True)
            root = etree.fromstring(content.encode(self.config.encoding), parser)
            return root
        except Exception as e:
            logger.error(f"XML解析失败: {e}")
            # 退回到标准库
            try:
                root = ET.fromstring(content)
                return root
            except Exception as e2:
                logger.error(f"标准库XML解析也失败: {e2}")
                raise
    
    def _extract_plc_elements(self, root: ET.Element, content: str):
        """提取PLC元素"""
        lines = content.split('\n')
        
        # 查找各种PLC元素
        self._extract_global_variables(root, lines)
        self._extract_data_types(root, lines)
        self._extract_function_blocks(root, lines)
        self._extract_programs(root, lines)
    
    def _extract_global_variables(self, root: ET.Element, lines: List[str]):
        """提取全局变量"""
        logger.info("提取全局变量...")
        
        # 查找全局变量声明
        for gvar_elem in root.iter():
            if 'GlobalVariable' in str(gvar_elem.tag) or 'Variable' in str(gvar_elem.tag):
                try:
                    name = self._get_element_name(gvar_elem)
                    if name:
                        line_start, line_end = self._find_element_lines(name, lines)
                        content = '\n'.join(lines[line_start:line_end+1])
                        dependencies = self._extract_dependencies_from_content(content)
                        
                        element = PLCElement(
                            name=name,
                            type="GlobalVariable",
                            content=content,
                            dependencies=dependencies,
                            line_start=line_start,
                            line_end=line_end,
                            size_estimate=self._estimate_tokens(content)
                        )
                        
                        self.global_variables[name] = element
                        
                except Exception as e:
                    logger.warning(f"提取全局变量失败: {e}")
                    continue
        
        logger.info(f"提取到 {len(self.global_variables)} 个全局变量")
    
    def _extract_data_types(self, root: ET.Element, lines: List[str]):
        """提取数据类型"""
        logger.info("提取数据类型...")
        
        for dt_elem in root.iter():
            if 'DataType' in str(dt_elem.tag) or 'Type' in str(dt_elem.tag):
                try:
                    name = self._get_element_name(dt_elem)
                    if name:
                        line_start, line_end = self._find_element_lines(name, lines)
                        content = '\n'.join(lines[line_start:line_end+1])
                        dependencies = self._extract_dependencies_from_content(content)
                        
                        element = PLCElement(
                            name=name,
                            type="DataType",
                            content=content,
                            dependencies=dependencies,
                            line_start=line_start,
                            line_end=line_end,
                            size_estimate=self._estimate_tokens(content)
                        )
                        
                        self.data_types[name] = element
                        
                except Exception as e:
                    logger.warning(f"提取数据类型失败: {e}")
                    continue
        
        logger.info(f"提取到 {len(self.data_types)} 个数据类型")
    
    def _extract_function_blocks(self, root: ET.Element, lines: List[str]):
        """提取功能块"""
        logger.info("提取功能块...")
        
        for fb_elem in root.iter():
            if 'FunctionBlock' in str(fb_elem.tag) or 'FB' in str(fb_elem.tag):
                try:
                    name = self._get_element_name(fb_elem)
                    if name:
                        line_start, line_end = self._find_element_lines(name, lines)
                        content = '\n'.join(lines[line_start:line_end+1])
                        dependencies = self._extract_dependencies_from_content(content)
                        
                        element = PLCElement(
                            name=name,
                            type="FunctionBlock",
                            content=content,
                            dependencies=dependencies,
                            line_start=line_start,
                            line_end=line_end,
                            size_estimate=self._estimate_tokens(content)
                        )
                        
                        self.function_blocks[name] = element
                        
                except Exception as e:
                    logger.warning(f"提取功能块失败: {e}")
                    continue
        
        logger.info(f"提取到 {len(self.function_blocks)} 个功能块")
    
    def _extract_programs(self, root: ET.Element, lines: List[str]):
        """提取程序"""
        logger.info("提取程序...")
        
        for prog_elem in root.iter():
            if 'Program' in str(prog_elem.tag) or 'POU' in str(prog_elem.tag):
                try:
                    name = self._get_element_name(prog_elem)
                    if name:
                        line_start, line_end = self._find_element_lines(name, lines)
                        content = '\n'.join(lines[line_start:line_end+1])
                        dependencies = self._extract_dependencies_from_content(content)
                        
                        element = PLCElement(
                            name=name,
                            type="Program",
                            content=content,
                            dependencies=dependencies,
                            line_start=line_start,
                            line_end=line_end,
                            size_estimate=self._estimate_tokens(content)
                        )
                        
                        self.programs[name] = element
                        
                except Exception as e:
                    logger.warning(f"提取程序失败: {e}")
                    continue
        
        logger.info(f"提取到 {len(self.programs)} 个程序")
    
    def _get_element_name(self, element: ET.Element) -> Optional[str]:
        """获取元素名称"""
        # 尝试多种属性名
        for attr in ['Name', 'name', 'id', 'Id']:
            if attr in element.attrib:
                return element.attrib[attr]
        
        # 尝试从子元素获取
        for child in element:
            if child.tag.endswith('Name') or child.tag.endswith('name'):
                return child.text
        
        return None
    
    def _find_element_lines(self, name: str, lines: List[str]) -> Tuple[int, int]:
        """查找元素在文件中的行号范围"""
        start_line = -1
        end_line = -1
        
        # 查找开始行
        for i, line in enumerate(lines):
            if name in line and ('Name=' in line or 'name=' in line):
                start_line = i
                break
        
        if start_line == -1:
            return 0, 0
        
        # 查找结束行
        bracket_count = 0
        in_element = False
        
        for i in range(start_line, len(lines)):
            line = lines[i]
            
            # 计算括号/标签嵌套
            if '<' in line and not line.strip().startswith('<!--'):
                if '</' in line:
                    bracket_count -= line.count('</')
                if '<' in line and not '</' in line:
                    bracket_count += line.count('<') - line.count('/>')
                    in_element = True
            
            if in_element and bracket_count <= 0:
                end_line = i
                break
        
        if end_line == -1:
            end_line = min(start_line + 50, len(lines) - 1)  # 默认50行
        
        return start_line, end_line
    
    def _extract_dependencies_from_content(self, content: str) -> Set[str]:
        """从内容中提取依赖"""
        dependencies = set()
        
        # 正则表达式匹配各种引用模式
        patterns = [
            r'(\w+)\.',  # 对象引用
            r'FB_(\w+)',  # 功能块引用
            r'GVL\.(\w+)',  # 全局变量列表引用
            r'TYPE\s+(\w+)',  # 类型引用
            r'VAR_GLOBAL\s+(\w+)',  # 全局变量引用
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    dependencies.update(match)
                else:
                    dependencies.add(match)
        
        # 过滤掉常见的关键字
        keywords = {'VAR', 'END_VAR', 'TYPE', 'END_TYPE', 'FUNCTION_BLOCK', 
                   'END_FUNCTION_BLOCK', 'PROGRAM', 'END_PROGRAM', 'IF', 'THEN', 
                   'ELSE', 'END_IF', 'FOR', 'TO', 'DO', 'END_FOR'}
        
        dependencies = {dep for dep in dependencies if dep not in keywords and len(dep) > 1}
        
        return dependencies
    
    def _estimate_tokens(self, content: str) -> int:
        """估算内容的token数量"""
        # 简单估算：平均每行15-20个token
        lines = content.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        return len(non_empty_lines) * 18  # 取中间值
    
    def _analyze_dependencies(self):
        """分析元素间的依赖关系"""
        logger.info("分析依赖关系...")
        
        all_elements = {**self.global_variables, **self.data_types, 
                       **self.function_blocks, **self.programs}
        
        for name, element in all_elements.items():
            deps = set()
            
            for dep_name in element.dependencies:
                if dep_name in all_elements:
                    deps.add(dep_name)
            
            self.dependencies[name] = deps
        
        logger.info(f"分析完成，共 {len(self.dependencies)} 个依赖关系")
    
    def _generate_shards(self) -> List[XMLShard]:
        """生成分片"""
        logger.info("生成分片...")
        
        shards = []
        
        # 数据定义分片（全局变量 + 数据类型）
        data_definition_shards = self._create_data_definition_shards()
        shards.extend(data_definition_shards)
        
        # 程序逻辑分片（功能块 + 程序）
        program_logic_shards = self._create_program_logic_shards()
        shards.extend(program_logic_shards)
        
        logger.info(f"生成 {len(shards)} 个分片")
        return shards
    
    def _create_data_definition_shards(self) -> List[XMLShard]:
        """创建数据定义分片"""
        shards = []
        current_elements = []
        current_token_count = 0
        shard_counter = 1
        
        # 合并全局变量和数据类型
        all_data_elements = list(self.global_variables.values()) + list(self.data_types.values())
        
        # 按依赖关系排序
        sorted_elements = self._sort_elements_by_dependencies(all_data_elements)
        
        for element in sorted_elements:
            if (current_token_count + element.size_estimate > 
                self.config.max_shard_lines * 18 and current_elements):
                
                # 创建分片
                shard = self._create_shard(
                    f"data_def_{shard_counter:03d}",
                    "data_definition",
                    current_elements
                )
                shards.append(shard)
                
                # 重置
                current_elements = []
                current_token_count = 0
                shard_counter += 1
            
            current_elements.append(element)
            current_token_count += element.size_estimate
        
        # 处理最后一个分片
        if current_elements:
            shard = self._create_shard(
                f"data_def_{shard_counter:03d}",
                "data_definition",
                current_elements
            )
            shards.append(shard)
        
        return shards
    
    def _create_program_logic_shards(self) -> List[XMLShard]:
        """创建程序逻辑分片"""
        shards = []
        current_elements = []
        current_token_count = 0
        shard_counter = 1
        
        # 合并功能块和程序
        all_program_elements = list(self.function_blocks.values()) + list(self.programs.values())
        
        # 按依赖关系排序
        sorted_elements = self._sort_elements_by_dependencies(all_program_elements)
        
        for element in sorted_elements:
            if (current_token_count + element.size_estimate > 
                self.config.max_shard_lines * 18 and current_elements):
                
                # 创建分片
                shard = self._create_shard(
                    f"prog_logic_{shard_counter:03d}",
                    "program_logic",
                    current_elements
                )
                shards.append(shard)
                
                # 重置
                current_elements = []
                current_token_count = 0
                shard_counter += 1
            
            current_elements.append(element)
            current_token_count += element.size_estimate
        
        # 处理最后一个分片
        if current_elements:
            shard = self._create_shard(
                f"prog_logic_{shard_counter:03d}",
                "program_logic",
                current_elements
            )
            shards.append(shard)
        
        return shards
    
    def _sort_elements_by_dependencies(self, elements: List[PLCElement]) -> List[PLCElement]:
        """按依赖关系排序元素"""
        # 简单的拓扑排序
        sorted_elements = []
        remaining = elements.copy()
        
        while remaining:
            # 找到没有未处理依赖的元素
            ready_elements = []
            for element in remaining:
                deps_ready = True
                for dep in element.dependencies:
                    if any(e.name == dep for e in remaining if e != element):
                        deps_ready = False
                        break
                
                if deps_ready:
                    ready_elements.append(element)
            
            if not ready_elements:
                # 如果存在循环依赖，随机选择一个
                ready_elements = [remaining[0]]
            
            sorted_elements.extend(ready_elements)
            for element in ready_elements:
                remaining.remove(element)
        
        return sorted_elements
    
    def _create_shard(self, shard_id: str, shard_type: str, elements: List[PLCElement]) -> XMLShard:
        """创建分片对象"""
        if not elements:
            return None
        
        # 计算依赖
        dependencies = set()
        for element in elements:
            dependencies.update(element.dependencies)
        
        # 移除内部依赖
        element_names = {e.name for e in elements}
        external_dependencies = dependencies - element_names
        
        # 生成上下文信息
        context_info = self._generate_context_for_shard(elements, external_dependencies)
        
        # 计算行号范围
        line_start = min(e.line_start for e in elements)
        line_end = max(e.line_end for e in elements)
        total_lines = sum(e.line_end - e.line_start + 1 for e in elements)
        token_estimate = sum(e.size_estimate for e in elements)
        
        return XMLShard(
            shard_id=shard_id,
            shard_type=shard_type,
            elements=elements,
            context_info=context_info,
            dependencies=external_dependencies,
            line_start=line_start,
            line_end=line_end,
            total_lines=total_lines,
            token_estimate=token_estimate
        )
    
    def _generate_context_for_shard(self, elements: List[PLCElement], dependencies: Set[str]) -> Dict[str, str]:
        """为分片生成上下文信息"""
        context = {}
        
        # 添加依赖元素的简要信息
        all_elements = {**self.global_variables, **self.data_types, 
                       **self.function_blocks, **self.programs}
        
        for dep_name in dependencies:
            if dep_name in all_elements:
                dep_element = all_elements[dep_name]
                # 只保留关键信息，避免上下文过大
                context[dep_name] = {
                    "type": dep_element.type,
                    "summary": dep_element.content[:200] + "..." if len(dep_element.content) > 200 else dep_element.content
                }
        
        return context
    
    def _generate_global_context(self) -> Dict[str, str]:
        """生成全局上下文"""
        context = {
            "total_elements": len(self.global_variables) + len(self.data_types) + 
                             len(self.function_blocks) + len(self.programs),
            "global_variables_count": len(self.global_variables),
            "data_types_count": len(self.data_types),
            "function_blocks_count": len(self.function_blocks),
            "programs_count": len(self.programs),
            "global_variable_names": list(self.global_variables.keys())[:50],  # 最多50个
            "data_type_names": list(self.data_types.keys())[:50],
            "function_block_names": list(self.function_blocks.keys())[:50],
            "program_names": list(self.programs.keys())[:50],
        }
        
        return context
    
    def export_shards_to_json(self, shards: List[XMLShard], output_dir: str):
        """导出分片到JSON文件"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for shard in shards:
            shard_data = {
                "shard_id": shard.shard_id,
                "shard_type": shard.shard_type,
                "elements": [asdict(element) for element in shard.elements],
                "context_info": shard.context_info,
                "dependencies": list(shard.dependencies),
                "line_start": shard.line_start,
                "line_end": shard.line_end,
                "total_lines": shard.total_lines,
                "token_estimate": shard.token_estimate
            }
            
            # 处理set类型
            for element_data in shard_data["elements"]:
                element_data["dependencies"] = list(element_data["dependencies"])
            
            file_path = output_path / f"{shard.shard_id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(shard_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"分片导出完成，共 {len(shards)} 个文件保存到 {output_dir}") 