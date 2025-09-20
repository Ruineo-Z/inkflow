# InkFlow 提示词管理

本目录包含InkFlow项目的所有AI生成提示词，按主题和功能分别组织在独立的文档中。

## 📁 文档结构

### 主题提示词
- **[wuxia.md](./wuxia.md)** - 武侠主题提示词
  - 世界观生成、主角生成、完整小说生成、第一章摘要生成

- **[scifi.md](./scifi.md)** - 科幻主题提示词
  - 世界观生成、主角生成、完整小说生成、第一章摘要生成

### 通用功能
- **[chapter_generation.md](./chapter_generation.md)** - 通用章节生成提示词
  - 后续章节摘要生成、章节正文和选项生成
  - 章节生成流程、选项设计策略

## 🔗 技术实现映射

| 提示词类型 | 文档位置 | 代码实现 |
|-----------|---------|----------|
| 武侠世界观生成 | wuxia.md | `app/services/novel_generator.py:26-44` |
| 武侠主角生成 | wuxia.md | `app/services/novel_generator.py:78-97` |
| 武侠完整小说生成 | wuxia.md | `app/services/novel_generator.py:133-150` |
| 武侠第一章摘要 | wuxia.md | `app/services/chapter_generator.py:41-63` |
| 科幻世界观生成 | scifi.md | `app/services/novel_generator.py:46-65` |
| 科幻主角生成 | scifi.md | `app/services/novel_generator.py:99-118` |
| 科幻完整小说生成 | scifi.md | `app/services/novel_generator.py:152-169` |
| 科幻第一章摘要 | scifi.md | `app/services/chapter_generator.py:66-87` |
| 后续章节摘要 | chapter_generation.md | `app/services/chapter_generator.py:98-153` |
| 章节正文生成 | chapter_generation.md | `app/services/chapter_generator.py:155-186` |

## 🎯 使用指南

### 新增主题
1. 在 `prompts/` 目录下创建新的主题文档（如 `fantasy.md`）
2. 参考现有主题文档的结构和格式
3. 在代码中实现对应的提示词逻辑
4. 更新本README文档的映射表

### 优化提示词
1. 直接编辑对应的主题文档
2. 在代码中同步更新提示词内容
3. 测试生成效果并持续优化

### 版本管理
- 所有提示词修改都应通过Git版本控制
- 重大修改前建议备份当前版本
- 记录优化前后的效果对比

## 📊 当前主题对比

| 特性 | 武侠主题 | 科幻主题 |
|------|---------|---------|
| 背景设定 | 历史朝代、武林江湖 | 未来时代、太空文明 |
| 核心元素 | 武功、门派、恩怨 | 科技、AI、外星文明 |
| 角色特色 | 侠义精神、武功修炼 | 科技素养、未来适应性 |
| 冲突类型 | 武林争斗、江湖恩怨 | 科技伦理、星际冲突 |
| 语言风格 | 古典文雅、武侠术语 | 现代科技、未来概念 |

## 🔄 版本历史

### v1.0.0 (当前版本)
- 初始版本，包含武侠和科幻两个主题
- 完整的小说生成和章节生成流程
- 基础的选项设计和上下文管理

### 计划优化
- [ ] 增加更多主题支持（奇幻、现代都市等）
- [ ] 优化选项设计的多样性和深度
- [ ] 加强角色情感和心理描写
- [ ] 提升世界观一致性检查
- [ ] 实现个性化推荐机制