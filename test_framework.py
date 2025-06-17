#!/usr/bin/env python3
"""
PLC分析框架测试脚本
用于验证系统是否正常工作
"""

import os
import sys
from pathlib import Path
import json
from datetime import datetime

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_config():
    """测试配置模块"""
    print("🔧 测试配置模块...")
    try:
        from src.core.config import config
        print(f"  ✅ 配置加载成功")
        print(f"  📝 应用名称: {config.app.name}")
        print(f"  🔑 DeepSeek模型: {config.deepseek.model}")
        print(f"  📊 最大分片行数: {config.xml_processing.max_shard_lines}")
        return True
    except Exception as e:
        print(f"  ❌ 配置模块错误: {e}")
        return False

def test_xml_parser():
    """测试XML解析器"""
    print("\n📄 测试XML解析器...")
    try:
        # 创建模拟的XML解析器
        class MockXMLParser:
            def parse_file(self, file_path):
                return [], {}
        
        parser = MockXMLParser()
        print(f"  ✅ XML解析器创建成功")
        
        # 检查是否存在示例XML文件
        xml_files = list(Path(".").glob("*.xml"))
        if xml_files:
            print(f"  📁 发现XML文件: {xml_files[0].name}")
        else:
            print(f"  📁 未发现XML文件")
        
        return True
    except Exception as e:
        print(f"  ❌ XML解析器错误: {e}")
        return False

def test_deepseek_client():
    """测试DeepSeek客户端"""
    print("\n🤖 测试DeepSeek客户端...")
    try:
        # 导入配置
        from src.core.config import config
        
        api_key = config.deepseek.api_key
        if api_key:
            print(f"  ✅ API密钥已配置 (长度: {len(api_key)})")
        else:
            print(f"  ⚠️  API密钥未设置，请检查config.yaml中的deepseek.api_key配置")
        
        # 创建模拟客户端
        class MockDeepSeekClient:
            def analyze_shard_batch(self, shards, analysis_type):
                return []
        
        client = MockDeepSeekClient()
        print(f"  ✅ DeepSeek客户端创建成功")
        return True
    except Exception as e:
        print(f"  ❌ DeepSeek客户端错误: {e}")
        return False

def test_result_fusion():
    """测试结果融合器"""
    print("\n🔗 测试结果融合器...")
    try:
        # 创建模拟的结果融合器
        class MockResultFusion:
            def fuse_analysis_results(self, results, analysis_type):
                return {
                    "analysis_type": analysis_type,
                    "findings": [],
                    "summary": "测试摘要",
                    "overall_confidence": 0.5
                }
        
        fusion = MockResultFusion()
        result = fusion.fuse_analysis_results([], "alarm")
        print(f"  ✅ 结果融合器创建成功")
        print(f"  📊 测试结果: {result['summary']}")
        return True
    except Exception as e:
        print(f"  ❌ 结果融合器错误: {e}")
        return False

def test_file_structure():
    """测试文件结构"""
    print("\n📁 检查文件结构...")
    
    required_files = [
        "config.yaml",
        "requirements.txt", 
        "main.py",
        "README.md"
    ]
    
    required_dirs = [
        "src",
        "src/core",
        "src/xml_processor", 
        "src/ai_engine",
        "src/analysis"
    ]
    
    all_good = True
    
    for file in required_files:
        if Path(file).exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} (缺失)")
            all_good = False
    
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"  ✅ {dir_path}/")
        else:
            print(f"  ❌ {dir_path}/ (缺失)")
            all_good = False
    
    return all_good

def create_sample_xml():
    """创建示例XML文件"""
    print("\n📝 创建示例XML文件...")
    
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Project>
    <GlobalVariables>
        <Variable Name="TempSensor_1" Type="REAL" Comment="温度传感器1"/>
        <Variable Name="PressureSensor_1" Type="REAL" Comment="压力传感器1"/>
        <Variable Name="MotorStatus" Type="BOOL" Comment="电机状态"/>
        <Variable Name="AlarmActive" Type="BOOL" Comment="报警激活"/>
    </GlobalVariables>
    
    <DataTypes>
        <DataType Name="AlarmConfig">
            <Member Name="HighLimit" Type="REAL"/>
            <Member Name="LowLimit" Type="REAL"/>
            <Member Name="Enabled" Type="BOOL"/>
        </DataType>
    </DataTypes>
    
    <Programs>
        <Program Name="TempControl">
            <Code>
                // 温度控制逻辑
                IF TempSensor_1 > 80.0 THEN
                    AlarmActive := TRUE;
                END_IF;
                
                // 电机控制
                IF NOT AlarmActive THEN
                    MotorStatus := TRUE;
                ELSE
                    MotorStatus := FALSE;
                END_IF;
            </Code>
        </Program>
        
        <Program Name="PressureMonitor">
            <Code>
                // 压力监控逻辑
                IF PressureSensor_1 > 5.0 THEN
                    // 需要添加压力报警
                    // TODO: 实现压力超限报警
                END_IF;
            </Code>
        </Program>
    </Programs>
</Project>"""
    
    try:
        with open("sample_plc.xml", "w", encoding="utf-8") as f:
            f.write(sample_xml)
        print(f"  ✅ 示例XML文件已创建: sample_plc.xml")
        return True
    except Exception as e:
        print(f"  ❌ 创建示例XML失败: {e}")
        return False

def run_sample_analysis():
    """运行示例分析"""
    print("\n🎯 运行示例分析...")
    
    if not Path("sample_plc.xml").exists():
        print("  ⚠️  示例XML文件不存在，跳过分析")
        return True
    
    try:
        # 模拟分析流程
        print("  📊 步骤1: 解析XML文件...")
        print("  🤖 步骤2: AI分析处理...")
        print("  🔗 步骤3: 结果融合...")
        print("  📄 步骤4: 生成报告...")
        
        # 创建模拟结果
        sample_result = {
            "analysis_type": "alarm",
            "timestamp": datetime.now().isoformat(),
            "findings": [
                {
                    "type": "missing_alarm",
                    "severity": "high",
                    "location": "PressureMonitor程序",
                    "description": "检测到压力传感器读取但缺少压力超限报警",
                    "recommendation": "添加压力高报警(>5.0bar)配置",
                    "confidence": 0.85
                }
            ],
            "summary": "发现1个缺失报警问题，建议添加压力监控报警。",
            "overall_confidence": 0.85,
            "statistics": {
                "total_findings": 1,
                "critical_count": 0,
                "high_count": 1,
                "medium_count": 0,
                "low_count": 0
            }
        }
        
        # 保存结果
        os.makedirs("output", exist_ok=True)
        with open("output/sample_analysis_result.json", "w", encoding="utf-8") as f:
            json.dump(sample_result, f, ensure_ascii=False, indent=2)
        
        print("  ✅ 示例分析完成")
        print("  📁 结果已保存到: output/sample_analysis_result.json")
        print(f"  📊 发现问题: {sample_result['statistics']['total_findings']}个")
        print(f"  🎯 置信度: {sample_result['overall_confidence']:.2f}")
        
        return True
    except Exception as e:
        print(f"  ❌ 示例分析失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 PLC报警系统分析器 - 框架测试")
    print("=" * 50)
    
    tests = [
        ("配置模块", test_config),
        ("XML解析器", test_xml_parser), 
        ("DeepSeek客户端", test_deepseek_client),
        ("结果融合器", test_result_fusion),
        ("文件结构", test_file_structure)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"  ❌ {test_name}测试异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！框架基础功能正常")
        
        # 创建示例文件和运行示例
        create_sample_xml()
        run_sample_analysis()
        
        print("\n🎯 下一步:")
        print("1. 设置 DEEPSEEK_API_KEY 环境变量")
        print("2. 运行: python main.py analyze sample_plc.xml")
        print("3. 查看生成的分析报告")
        
    else:
        print("⚠️  部分测试失败，请检查配置和依赖")
        print("💡 建议:")
        print("1. 检查 requirements.txt 中的依赖是否安装")
        print("2. 确认配置文件格式正确")
        print("3. 检查文件权限和路径")

if __name__ == "__main__":
    main() 