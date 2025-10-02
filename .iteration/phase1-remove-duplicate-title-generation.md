# Phase 1: 移除章节正文生成时的重复title生成

## 问题描述

当前章节生成流程中,title被生成了两次:
1. **Step 1 (摘要生成)**: `ChapterSummary` 包含 `title` 字段
2. **Step 2 (正文生成)**: `ChapterFullContent` 也包含 `title` 字段

虽然提示词中会参考第一步的title,但AI仍被要求重新生成title,可能导致:
- 标题不一致
- 浪费token
- 增加数据处理复杂度

## 解决方案

**统一使用摘要阶段生成的title,移除正文生成时的title字段**

## 变更清单

### 1. 修改Schema定义
**文件**: `app/schemas/chapter.py`

**修改前**:
```python
class ChapterFullContent(BaseModel):
    """完整章节内容模型（流式输出用）"""
    title: str = Field(description="章节标题")
    content: str = Field(description="章节正文内容")
    options: List[ChapterOption] = Field(description="三个选择选项")
```

**修改后**:
```python
class ChapterFullContent(BaseModel):
    """完整章节内容模型（流式输出用）"""
    content: str = Field(description="章节正文内容")
    options: List[ChapterOption] = Field(description="三个选择选项")
    # title字段已移除,统一使用ChapterSummary中的title
```

### 2. 修改提示词生成逻辑
**文件**: `app/services/chapter_generator.py`

**修改位置**: `_build_chapter_content_prompt` 方法 (第158-208行)

**修改前** (第204-206行):
```python
请用JSON格式返回，包含title、content、options字段。
options数组中每个选项包含：text、impact_hint、tags字段。
tags字段包含上述五个标签维度。
```

**修改后**:
```python
请用JSON格式返回，包含content、options字段。
options数组中每个选项包含：text、impact_hint、tags字段。
tags字段包含上述五个标签维度。
```

### 3. 修改complete事件组装逻辑
**文件**: `app/services/chapter_generator.py`

**修改位置1**: `generate_first_chapter_stream` 方法 (第284-295行)

**修改前**:
```python
elif stream_chunk.chunk_type == "complete":
    logger.info(f"✅ Step 2 完成: 章节正文和选项生成成功")
    # 添加摘要信息到完成数据中
    complete_data = stream_chunk.data['result']
    complete_data['summary'] = summary.dict()

    # 统计信息
    content_length = len(complete_data.get('content', ''))
    options_count = len(complete_data.get('options', []))
    logger.info(f"📊 正文字符数: {content_length}, 选项数量: {options_count}")

    yield f"event: complete\ndata: {json_dumps_chinese(complete_data)}\n\n"
```

**修改后**:
```python
elif stream_chunk.chunk_type == "complete":
    logger.info(f"✅ Step 2 完成: 章节正文和选项生成成功")
    # 组装完整数据
    complete_data = stream_chunk.data['result']
    complete_data['title'] = summary.title  # 使用摘要阶段的title
    complete_data['summary'] = summary.dict()

    # 统计信息
    content_length = len(complete_data.get('content', ''))
    options_count = len(complete_data.get('options', []))
    logger.info(f"📊 正文字符数: {content_length}, 选项数量: {options_count}")

    yield f"event: complete\ndata: {json_dumps_chinese(complete_data)}\n\n"
```

**修改位置2**: `generate_next_chapter_stream` 方法 (第372-383行)

**修改前**:
```python
elif stream_chunk.chunk_type == "complete":
    logger.info(f"✅ Step 2 完成: 后续章节正文和选项生成成功")
    # 添加摘要信息到完成数据中
    complete_data = stream_chunk.data['result']
    complete_data['summary'] = summary.dict()

    # 统计信息
    content_length = len(complete_data.get('content', ''))
    options_count = len(complete_data.get('options', []))
    logger.info(f"📊 正文字符数: {content_length}, 选项数量: {options_count}")

    yield f"event: complete\ndata: {json_dumps_chinese(complete_data)}\n\n"
```

**修改后**:
```python
elif stream_chunk.chunk_type == "complete":
    logger.info(f"✅ Step 2 完成: 后续章节正文和选项生成成功")
    # 组装完整数据
    complete_data = stream_chunk.data['result']
    complete_data['title'] = summary.title  # 使用摘要阶段的title
    complete_data['summary'] = summary.dict()

    # 统计信息
    content_length = len(complete_data.get('content', ''))
    options_count = len(complete_data.get('options', []))
    logger.info(f"📊 正文字符数: {content_length}, 选项数量: {options_count}")

    yield f"event: complete\ndata: {json_dumps_chinese(complete_data)}\n\n"
```

## 预期效果

1. ✅ **数据一致性**: title只在摘要阶段生成一次,保证一致性
2. ✅ **节省token**: 减少AI重复生成相同内容
3. ✅ **简化逻辑**: 后续处理只需信任summary.title
4. ✅ **向后兼容**: complete事件的数据结构不变(仍包含title字段)

## 测试验证

修改后需要验证:
1. 摘要事件正常返回title
2. complete事件包含正确的title(来自summary)
3. 生成的章节数据在数据库中title正确
4. 前端显示的标题正确

## 风险评估

- **低风险**: 修改只涉及内部数据流转,对外接口不变
- **兼容性**: complete事件仍包含title字段,前端无需修改
