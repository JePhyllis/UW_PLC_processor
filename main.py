"""
PLC报警系统分析器 - 主应用程序
基于DeepSeek R1的智能PLC代码分析工具
"""

import os
import sys
import argparse
import time
from pathlib import Path
from loguru import logger
import uvicorn
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.config import config
from src.xml_processor.parser import PLCXMLParser
from src.ai_engine.deepseek_client import DeepSeekClient
from src.analysis.result_fusion import ResultFusion


class PLCAnalyzer:
    """PLC分析器主类"""
    
    def __init__(self):
        self.parser = PLCXMLParser()
        self.ai_client = DeepSeekClient()
        self.result_fusion = ResultFusion()
        
    def analyze_file(self, xml_file: str, output_dir: str = "output", analysis_type: str = "alarm"):
        """
        分析PLC XML文件
        
        Args:
            xml_file: XML文件路径
            output_dir: 输出目录
            analysis_type: 分析类型 (alarm, safety, logic)
        """
        logger.info(f"开始分析文件: {xml_file}")
        start_time = time.time()
        
        # 验证配置
        if not config.validate():
            logger.error("配置验证失败，请检查配置文件和环境变量")
            return False
        
        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        try:
            # 1. 解析XML文件并生成分片
            logger.info("步骤1: 解析XML文件...")
            shards, global_context = self.parser.parse_file(xml_file)
            
            if not shards:
                logger.error("未能生成有效的分片")
                return False
            
            # 导出分片到JSON（用于调试）
            shards_dir = output_path / "shards"
            self.parser.export_shards_to_json(shards, str(shards_dir))
            
            # 2. 批量分析分片
            logger.info(f"步骤2: 使用DeepSeek R1分析 {len(shards)} 个分片...")
            
            # 将分片转换为字典格式
            shard_dicts = []
            for shard in shards:
                shard_dict = {
                    "shard_id": shard.shard_id,
                    "shard_type": shard.shard_type,
                    "elements": [
                        {
                            "name": elem.name,
                            "type": elem.type,
                            "content": elem.content,
                            "dependencies": list(elem.dependencies)
                        }
                        for elem in shard.elements
                    ],
                    "context_info": shard.context_info,
                    "dependencies": list(shard.dependencies)
                }
                shard_dicts.append(shard_dict)
            
            # 分批处理以避免API限制
            batch_size = config.parallel.batch_size
            all_results = []
            
            for i in range(0, len(shard_dicts), batch_size):
                batch = shard_dicts[i:i+batch_size]
                logger.info(f"处理批次 {i//batch_size + 1}/{(len(shard_dicts) + batch_size - 1)//batch_size}")
                
                batch_results = self.ai_client.analyze_shard_batch(batch, analysis_type)
                all_results.extend(batch_results)
                
                # 批次间短暂延迟
                if i + batch_size < len(shard_dicts):
                    time.sleep(2)
            
            # 3. 融合结果
            logger.info("步骤3: 融合分析结果...")
            fused_result = self.result_fusion.fuse_analysis_results(all_results, analysis_type)
            
            # 4. 生成报告
            logger.info("步骤4: 生成报告...")
            
            # JSON报告
            json_report_path = output_path / f"analysis_report_{analysis_type}.json"
            self.result_fusion.export_results_to_json(fused_result, str(json_report_path))
            
            # HTML报告
            html_report_path = output_path / f"analysis_report_{analysis_type}.html"
            self.result_fusion.generate_html_report(fused_result, str(html_report_path))
            
            # 5. 输出摘要
            total_time = time.time() - start_time
            logger.info(f"分析完成! 总耗时: {total_time:.2f}秒")
            logger.info(f"发现 {len(fused_result.findings)} 个问题")
            logger.info(f"整体置信度: {fused_result.overall_confidence:.2f}")
            logger.info(f"报告已生成: {html_report_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"分析过程中发生错误: {e}")
            return False
    
    def start_web_server(self, host: str = "0.0.0.0", port: int = 8000):
        """启动Web服务器"""
        logger.info(f"启动Web服务器: http://{host}:{port}")
        
        try:
            from src.web.app import app
            uvicorn.run(app, host=host, port=port, reload=config.app.debug)
        except ImportError:
            logger.error("Web模块未实现，请使用命令行模式")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="PLC报警系统分析器")
    
    # 命令选择
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 分析命令
    analyze_parser = subparsers.add_parser("analyze", help="分析PLC XML文件")
    analyze_parser.add_argument("file", help="XML文件路径")
    analyze_parser.add_argument("--output", "-o", default="output", help="输出目录")
    analyze_parser.add_argument("--type", "-t", choices=["alarm", "safety", "logic"], 
                               default="alarm", help="分析类型")
    
    # Web服务命令
    web_parser = subparsers.add_parser("web", help="启动Web界面")
    web_parser.add_argument("--host", default="0.0.0.0", help="服务器主机")
    web_parser.add_argument("--port", type=int, default=8000, help="服务器端口")
    
    # 配置检查命令
    subparsers.add_parser("check", help="检查配置")
    
    args = parser.parse_args()
    
    # 配置日志
    logger.remove()
    logger.add(sys.stderr, level=config.app.log_level)
    logger.add("logs/plc_analyzer_{time}.log", rotation="1 day", level="DEBUG")
    
    # 创建分析器实例
    analyzer = PLCAnalyzer()
    
    if args.command == "analyze":
        # 检查文件是否存在
        if not os.path.exists(args.file):
            logger.error(f"文件不存在: {args.file}")
            sys.exit(1)
        
        success = analyzer.analyze_file(args.file, args.output, args.type)
        sys.exit(0 if success else 1)
        
    elif args.command == "web":
        analyzer.start_web_server(args.host, args.port)
        
    elif args.command == "check":
        logger.info("检查配置...")
        if config.validate():
            logger.info("配置正确")
        else:
            logger.error("配置有误")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 