# 脚本使用说明

## 章节生成测试脚本

`test_chapter_generation.py` 是一个用于测试章节生成API的命令行工具，支持流式输出展示。

### 功能特点

- 🌊 **流式输出**: 实时展示生成过程
- 🎨 **富文本显示**: 使用 Rich 库提供美观的终端输出
- 📊 **进度指示**: 显示生成状态和进度
- 🔄 **错误处理**: 完善的错误处理和提示

### 安装依赖

```bash
uv add httpx click rich
```

### 使用方法

#### 1. 生成第一章

```bash
python scripts/test_chapter_generation.py first <novel_id>
```

示例：
```bash
python scripts/test_chapter_generation.py first 1
```

#### 2. 生成后续章节

```bash
python scripts/test_chapter_generation.py next <novel_id> <option_id>
```

示例：
```bash
python scripts/test_chapter_generation.py next 1 5
```

#### 3. 指定服务器地址和认证

```bash
python scripts/test_chapter_generation.py --base-url http://localhost:8001 --token your_token first 1
```

#### 4. 查看帮助

```bash
python scripts/test_chapter_generation.py --help
python scripts/test_chapter_generation.py first --help
python scripts/test_chapter_generation.py next --help
```

### 输出示例

脚本会显示：

1. **连接状态**: 显示连接进度和状态
2. **章节摘要**: 生成的章节概要信息
3. **实时内容**: 流式显示生成的文本内容
4. **章节选项**: 显示可选的下一步选项
5. **完整结果**: 最终的完整章节内容

### 注意事项

- 确保 FastAPI 服务器已启动（默认端口 8001）
- 如果需要认证，请提供有效的 token
- 生成过程可能需要较长时间，请耐心等待
- 如果遇到网络问题，请检查服务器状态

### 故障排除

1. **连接失败**: 检查服务器是否启动，端口是否正确
2. **认证错误**: 检查 token 是否有效
3. **超时错误**: 生成时间较长，可以等待或重试
4. **JSON 解析错误**: 可能是服务器返回了非标准格式的数据