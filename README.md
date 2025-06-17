# PLC报警系统分析器

基于DeepSeek R1的智能PLC代码分析工具，专门用于分析PLC XML文件中的报警系统配置和潜在问题。

## 🎯 主要功能

- **智能XML分片处理**: 将大型PLC XML文件智能分割为适合LLM处理的小片段
- **并行AI分析**: 使用DeepSeek R1并行分析多个代码分片
- **报警缺失检测**: 自动识别缺失的关键报警配置
- **安全分析**: 检查安全相关的逻辑和功能
- **逻辑验证**: 验证程序逻辑的正确性和完整性
- **智能结果融合**: 将多个分片的分析结果智能合并
- **可视化报告**: 生成HTML和JSON格式的分析报告

## 🏗️ 系统架构

```
├── XML解析器
│   ├── 智能分片生成
│   └── 依赖关系分析
├── DeepSeek R1引擎
│   ├── 并行API调用
│   ├── 错误处理重试
│   └── 结果缓存
├── 分析模块
│   ├── 报警系统分析
│   ├── 安全功能分析
│   └── 逻辑正确性分析
└── 结果融合器
    ├── 发现去重合并
    ├── 置信度计算
    └── 报告生成
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd UW_PLC_processor

# 安装依赖
pip install -r requirements.txt

# 创建环境变量文件
cp .env.example .env
```

### 2. 配置设置

编辑 `.env` 文件，设置必要的环境变量：

```bash
# DeepSeek API配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# 数据库配置（可选）
NEO4J_PASSWORD=your_neo4j_password
```

编辑 `config.yaml` 文件以调整系统参数：

```yaml
deepseek:
  max_concurrent_requests: 20  # 并发请求数
  max_tokens: 32000           # 上下文窗口大小
  temperature: 0.1            # 生成温度

xml_processing:
  max_shard_lines: 1500      # 最大分片行数
  overlap_lines: 100         # 分片重叠行数
```

### 3. 运行分析

```bash
# 分析PLC XML文件
python main.py analyze your_plc_file.xml

# 指定输出目录和分析类型
python main.py analyze your_plc_file.xml --output results --type alarm

# 启动Web界面
python main.py web

# 检查配置
python main.py check
```

## 📊 分析类型

### 1. 报警系统分析 (alarm)
- 识别现有报警配置
- 发现缺失的关键报警
- 评估报警设置的合理性
- 检查报警管理最佳实践

### 2. 安全功能分析 (safety)
- 检查安全相关逻辑
- 验证安全联锁功能
- 分析故障检测机制
- 评估冗余设计

### 3. 逻辑正确性分析 (logic)
- 验证程序逻辑正确性
- 检查条件判断完整性
- 分析状态机逻辑
- 识别潜在逻辑错误

## 📁 项目结构

```
UW_PLC_processor/
├── src/                    # 源代码
│   ├── core/              # 核心模块
│   │   └── config.py      # 配置管理
│   ├── xml_processor/     # XML处理
│   │   └── parser.py      # XML解析器
│   ├── ai_engine/         # AI引擎
│   │   └── deepseek_client.py  # DeepSeek客户端
│   ├── analysis/          # 分析模块
│   │   └── result_fusion.py   # 结果融合
│   └── web/               # Web界面
├── config.yaml            # 配置文件
├── requirements.txt       # 依赖包列表
├── main.py               # 主程序入口
└── README.md             # 项目说明
```

## 🔧 配置说明

### XML处理配置
- `max_shard_lines`: 单个分片的最大行数
- `min_shard_lines`: 单个分片的最小行数
- `overlap_lines`: 分片间的重叠行数
- `target_shard_count`: 目标分片数量

### 并行处理配置
- `max_workers`: 最大工作线程数
- `batch_size`: 批处理大小
- `worker_timeout`: 工作超时时间

### AI分析配置
- `few_shot_examples`: Few-shot示例数量
- `confidence_threshold`: 置信度阈值
- `max_analysis_depth`: 最大分析深度

## 📊 输出报告

### JSON报告
包含完整的分析结果数据，可用于进一步处理：
```json
{
  "analysis_type": "alarm",
  "findings": [...],
  "summary": "分析摘要",
  "overall_confidence": 0.85,
  "statistics": {...}
}
```

### HTML报告
可视化的分析报告，包含：
- 分析摘要
- 详细发现列表
- 统计图表
- 改进建议

## 🎯 核心特性

### 智能分片处理
- **依赖感知分片**: 保持相关代码在同一分片中
- **上下文保留**: 维护必要的依赖信息
- **大小优化**: 根据token限制智能调整分片大小

### 并行处理优化
- **批量处理**: 并行处理多个分片提高效率
- **限流控制**: 避免API限制和过载
- **错误重试**: 自动重试失败的请求

### 结果质量保证
- **置信度评估**: 对每个发现计算置信度
- **结果去重**: 智能合并相似的发现
- **交叉验证**: 通过多分片验证提高准确性

## 🔍 分析示例

### 缺失报警检测
```
发现: 温度传感器TT_001读取但缺少超温报警
严重程度: 高
建议: 添加温度高报警(>80°C)和高高报警(>95°C)
置信度: 0.92
```

### 安全问题识别
```
发现: 急停按钮逻辑可能存在旁路风险
严重程度: 严重
建议: 增加安全继电器冗余设计
置信度: 0.88
```

## 📈 性能优化

### 处理速度
- 单线程处理: ~60分钟
- 并行处理(20线程): ~30-45分钟
- 效率提升: 70-80%

### 内存使用
- 分片加载: 减少内存峰值
- 缓存策略: 重用分析结果
- 垃圾回收: 及时释放资源

## 🛠️ 故障排除

### 常见问题

1. **API密钥错误**
   ```bash
   错误: DEEPSEEK_API_KEY environment variable is required
   解决: 检查.env文件中的API密钥设置
   ```

2. **内存不足**
   ```bash
   解决: 减少max_workers或batch_size参数
   ```

3. **网络超时**
   ```bash
   解决: 增加request_timeout参数值
   ```

## 📝 开发说明

### 添加新的分析类型
1. 在 `deepseek_client.py` 中添加新的系统提示词
2. 更新 `result_fusion.py` 中的结果处理逻辑
3. 在 `main.py` 中添加命令行选项

### 扩展XML解析
1. 在 `parser.py` 中添加新的元素提取方法
2. 更新依赖关系分析逻辑
3. 调整分片生成策略

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 发起 Pull Request

## 📄 许可证

MIT License

## 📞 联系方式

如有问题或建议，请通过以下方式联系：
- 邮箱: [your-email@example.com]
- 问题追踪: GitHub Issues

---

**注意**: 本工具仅用于辅助分析，不能替代人工审查。在生产环境中使用前，请务必进行充分的验证和测试。 