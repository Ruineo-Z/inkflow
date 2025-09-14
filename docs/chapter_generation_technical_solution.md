# 小说章节生成技术实现方案

## 技术架构设计

### 1. 数据模型设计

#### Chapter模型（章节表）
```
- id: 主键
- novel_id: 外键，关联小说
- chapter_number: 章节序号
- title: 章节标题
- summary: 章节摘要
- content: 章节正文
- created_at: 创建时间
- updated_at: 更新时间
```

#### Option模型（选项表）
```
- id: 主键
- chapter_id: 外键，关联章节
- option_text: 选项文本
- option_order: 选项顺序（1,2,3）
- impact_description: 对后续剧情的影响描述
```

#### UserChoice模型（用户选择记录表）
```
- id: 主键
- user_id: 用户ID
- chapter_id: 章节ID
- option_id: 选择的选项ID
- created_at: 选择时间
```

### 2. Pydantic模型设计

#### 章节摘要模型
```python
class ChapterSummary(BaseModel):
    title: str = Field(description="章节标题")
    summary: str = Field(description="章节摘要")
    key_events: List[str] = Field(description="关键事件")
    conflicts: List[str] = Field(description="冲突点")
```

#### 章节完整内容模型（流式输出用）
```python
class ChapterOption(BaseModel):
    text: str = Field(description="选项文本")
    impact_hint: str = Field(description="选择影响提示")

class ChapterFullContent(BaseModel):
    title: str = Field(description="章节标题")
    content: str = Field(description="章节正文内容")
    options: List[ChapterOption] = Field(description="三个选择选项")
```

### 3. 服务层设计

#### ChapterGeneratorService
```python
class ChapterGeneratorService:
    # 生成第一章摘要
    async def generate_first_chapter_summary(novel_info) -> ChapterSummary

    # 生成非第一章摘要
    async def generate_chapter_summary(context_info, user_choice) -> ChapterSummary

    # 生成章节完整内容（流式）
    async def generate_chapter_content_stream(summary, context) -> AsyncGenerator[ChapterFullContent]

    # 获取章节上下文（前五章+其余摘要）
    async def get_chapter_context(novel_id, current_chapter_number) -> ContextInfo
```

#### ChapterService（数据库操作）
```python
class ChapterService:
    async def create_chapter(chapter_data) -> Chapter
    async def create_options(chapter_id, options_data) -> List[Option]
    async def get_chapter_history(novel_id, limit=5) -> List[Chapter]
    async def get_chapter_summaries(novel_id, exclude_recent=5) -> List[Dict]
    async def record_user_choice(user_id, chapter_id, option_id) -> UserChoice
```

### 4. API设计

#### 生成章节接口
```
POST /api/v1/novels/{novel_id}/chapters
Content-Type: application/json

请求体:
{
    "selected_option_id": 123  # 可选，第一章时为空
}

响应:
{
    "chapter_id": 456,
    "stream_url": "/api/v1/chapters/456/stream"
}
```

#### 流式输出接口
```
GET /api/v1/chapters/{chapter_id}/stream
Accept: text/event-stream

SSE流式响应:
event: summary
data: {"title": "...", "summary": "..."}

event: content_chunk
data: {"content": "章节内容片段..."}

event: options
data: {"options": [...]}

event: complete
data: {"message": "生成完成"}
```

### 5. AI调用策略

#### 第一章生成
```python
# 步骤1: 生成摘要（结构化输出）
summary_prompt = build_first_chapter_summary_prompt(world_setting, protagonist)
summary = await kimi_service.generate_structured_output(ChapterSummary, summary_prompt)

# 步骤2: 生成内容+选项（结构化流式输出）
content_prompt = build_chapter_content_prompt(summary, world_setting, protagonist)
async for chunk in kimi_service.generate_structured_stream(ChapterFullContent, content_prompt):
    yield chunk
```

#### 非第一章生成
```python
# 步骤1: 生成摘要
context = await get_chapter_context(novel_id, chapter_number)
summary_prompt = build_chapter_summary_prompt(context, selected_option)
summary = await kimi_service.generate_structured_output(ChapterSummary, summary_prompt)

# 步骤2: 生成内容+选项（流式）
content_prompt = build_chapter_content_prompt(summary, context)
async for chunk in kimi_service.generate_structured_stream(ChapterFullContent, content_prompt):
    yield chunk
```

### 6. 上下文管理策略

#### ContextInfo模型
```python
class ContextInfo(BaseModel):
    world_setting: str
    protagonist_info: str
    recent_chapters: List[Chapter]  # 前五章完整内容
    chapter_summaries: List[Dict]   # 其余章节摘要
    selected_option: Optional[str]  # 用户选择的选项
```

#### 上下文获取逻辑
```python
async def get_chapter_context(novel_id: int, chapter_number: int) -> ContextInfo:
    # 获取小说基础信息
    novel = await get_novel_by_id(novel_id)

    # 获取前5章完整内容
    recent_chapters = await get_recent_chapters(novel_id, limit=5)

    # 获取其余章节摘要
    older_summaries = await get_chapter_summaries(novel_id, exclude_recent=5)

    return ContextInfo(...)
```

### 7. 流式输出实现

#### FastAPI流式响应
```python
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

@router.post("/novels/{novel_id}/chapters/{chapter_id}/stream")
async def stream_chapter_generation(chapter_id: int):
    async def generate():
        # 生成章节内容流
        async for chunk in chapter_service.generate_chapter_stream(chapter_id):
            yield {
                "event": chunk.event_type,
                "data": chunk.data
            }

    return EventSourceResponse(generate())
```

### 8. 错误处理和重试机制

#### 生成失败处理
```python
class ChapterGenerationError(Exception):
    pass

async def generate_chapter_with_retry(novel_id: int, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return await generate_chapter(novel_id)
        except ChapterGenerationError as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # 指数退避
```

### 9. 缓存和优化

#### 上下文缓存
```python
# 使用Redis缓存上下文信息
@cached(ttl=3600)  # 缓存1小时
async def get_chapter_context_cached(novel_id: int, chapter_number: int):
    return await get_chapter_context(novel_id, chapter_number)
```

#### 流式输出缓存
```python
# 将生成的内容同步保存到数据库
async def save_generated_content(chapter_id: int, content: str, options: List[Dict]):
    await chapter_service.update_chapter_content(chapter_id, content)
    await chapter_service.create_chapter_options(chapter_id, options)
```

### 10. 数据库性能优化

#### 索引设计
```sql
-- 章节查询优化
CREATE INDEX idx_chapters_novel_number ON chapters(novel_id, chapter_number);
CREATE INDEX idx_options_chapter ON options(chapter_id, option_order);
CREATE INDEX idx_user_choices_user_chapter ON user_choices(user_id, chapter_id);
```

#### 查询优化
```python
# 使用预加载减少N+1查询
async def get_chapters_with_options(novel_id: int):
    return await session.execute(
        select(Chapter)
        .options(selectinload(Chapter.options))
        .where(Chapter.novel_id == novel_id)
    )
```

## 实现优先级

1. **Phase 1**: 基础数据模型和服务层
2. **Phase 2**: AI调用和章节生成核心逻辑
3. **Phase 3**: API接口和流式输出
4. **Phase 4**: 错误处理和性能优化
5. **Phase 5**: 缓存和监控

这个方案确保了功能的完整性、性能的可扩展性，以及用户体验的流畅性。