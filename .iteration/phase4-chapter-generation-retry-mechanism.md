# Phase 4: 章节生成失败重试机制

## 前置依赖

**本功能基于Phase 3 (流式生成解耦) 实现,复用其核心生成能力**

## 功能概述

在Phase 3的基础上,增加失败状态处理:
- 检测失败章节
- 清理失败数据
- 复用Phase 3的生成流程

## 核心设计原则

1. **复用Phase 3** - 不重复实现生成逻辑
2. **保留用户选择** - 删除失败章节时,不删除上一章的UserChoice
3. **最简清理** - 只做必要的数据清理

## 数据关系说明

```
Chapter 1000 [COMPLETED]
  ├─ Option 10001
  ├─ Option 10002 ← 用户选择了这个
  └─ Option 10003

UserChoice(user=1, chapter=1000, option=10002) ← 保留这个
  ↓ 触发生成

Chapter 1001 [FAILED] ← 删除这个
  └─ (没有Options,因为还没完成)
```

**关键点**:
- UserChoice.chapter_id = 1000 (用户在Chapter 1000做的选择)
- 删除Chapter 1001不影响UserChoice
- 重试时读取UserChoice,复用Phase 3的生成逻辑

## 实现方案

### 统一生成接口增强

在Phase 3的`/generate`接口基础上,增加失败状态处理:

```python
@router.post("/{novel_id}/chapters/generate")
async def generate_chapter(
    novel_id: int,
    request: GenerateChapterRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    统一的章节生成接口
    Phase 3提供: 首次生成、断线重连
    Phase 4增加: 失败重试
    """
    chapter_number = request.chapter_number

    # 1. chapter_number=0 表示最新章节
    if chapter_number == 0:
        latest_chapter = await chapter_service.get_latest_chapter(novel_id)
        if latest_chapter:
            target_chapter = latest_chapter
        else:
            chapter_number = 1
            target_chapter = None
    else:
        target_chapter = await chapter_service.get_chapter_by_number(
            novel_id, chapter_number
        )

    # 2. 根据章节状态路由
    if target_chapter:
        if target_chapter.status == ChapterStatus.FAILED:
            # ====== Phase 4: 失败重试 ======
            return StreamingResponse(
                handle_failed_retry(
                    target_chapter,
                    novel_id,
                    current_user_id,
                    db
                ),
                media_type="text/event-stream"
            )

        elif target_chapter.status == ChapterStatus.GENERATING:
            # Phase 3: 断线重连
            return StreamingResponse(
                stream_from_redis(target_chapter.id),
                media_type="text/event-stream"
            )

        elif target_chapter.status == ChapterStatus.COMPLETED:
            raise HTTPException(400, "章节已生成完成")

    # Phase 3: 首次生成
    return StreamingResponse(
        start_new_generation(novel_id, chapter_number, current_user_id, db),
        media_type="text/event-stream"
    )
```

### 失败重试核心逻辑

```python
async def handle_failed_retry(
    failed_chapter: Chapter,
    novel_id: int,
    user_id: int,
    db: AsyncSession
) -> AsyncGenerator[str, None]:
    """
    处理失败章节的重试

    策略: 清理失败数据 + 复用Phase 3的首次生成逻辑
    """
    chapter_id = failed_chapter.id
    chapter_number = failed_chapter.chapter_number

    # ====== Phase 4: 失败清理 ======

    # 1. 删除失败的章节记录 (PostgreSQL)
    await chapter_service.delete_chapter(chapter_id)
    await db.commit()

    # 2. 删除Redis数据 (如果存在)
    try:
        await ChapterCacheService.delete_generating_content(chapter_id)
    except Exception:
        pass  # Redis数据可能已不存在,忽略错误

    # ====== 复用Phase 3: 首次生成逻辑 ======

    # 直接调用Phase 3的生成流程
    async for event in start_new_generation(novel_id, chapter_number, user_id, db):
        yield event
```

**关键点**:
- ✅ Phase 4只负责"删除"
- ✅ 删除后直接`async for`复用Phase 3的生成器
- ✅ 不重复实现任何生成逻辑

### 数据清理实现

```python
class ChapterService:

    async def delete_chapter(self, chapter_id: int) -> None:
        """
        删除章节

        级联删除:
        - Options (失败时不会有)
        - UserChoices (失败时不会有)
        """
        result = await self.db.execute(
            select(Chapter).where(Chapter.id == chapter_id)
        )
        chapter = result.scalar_one_or_none()

        if chapter:
            await self.db.delete(chapter)
            # cascade会自动删除关联数据
```

## 前端UI设计

### 失败状态检测

```javascript
const ReadingPage = () => {
  const [pageState, setPageState] = useState('loading');

  useEffect(() => {
    const fetchChapterStatus = async () => {
      const chapter = await api.getLatestChapter(novelId);

      if (!chapter) {
        // 没有章节,需要生成第一章
        generateChapter();
      } else if (chapter.status === 'failed') {
        // Phase 4: 失败状态
        setPageState('failed');
      } else if (chapter.status === 'generating') {
        // Phase 3: 生成中,重连
        generateChapter();
      } else if (chapter.status === 'completed') {
        // 已完成,显示章节
        setPageState('completed');
        setChapterData(chapter);
      }
    };

    fetchChapterStatus();
  }, [novelId]);

  // 渲染失败UI
  if (pageState === 'failed') {
    return <FailedUI onRetry={handleRetry} />;
  }

  // ... 其他状态渲染
};
```

### 失败UI组件

```jsx
const FailedUI = ({ onRetry }) => {
  const [retrying, setRetrying] = useState(false);

  const handleRetry = async () => {
    setRetrying(true);
    try {
      await onRetry();  // 调用统一的generateChapter函数
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className="generation-failed">
      <div className="error-icon">
        <Icon type="exclamation-circle" size="large" color="red" />
      </div>

      <div className="error-message">
        <h3>章节生成失败</h3>
        <p>生成过程中遇到了问题,请重试</p>
      </div>

      <div className="actions">
        <Button
          type="primary"
          onClick={handleRetry}
          loading={retrying}
        >
          重新生成
        </Button>

        <Button onClick={() => navigate(-1)}>
          返回上一章
        </Button>
      </div>
    </div>
  );
}
```

### 重试逻辑 (复用Phase 3)

```javascript
const handleRetry = async () => {
  // 直接调用Phase 3的生成函数
  // 后端会自动检测failed状态并清理
  await generateChapter();
};

const generateChapter = async () => {
  // Phase 3定义的统一生成函数
  const eventSource = new EventSource(
    `/api/v1/novels/${novelId}/chapters/generate`,
    {
      method: 'POST',
      body: JSON.stringify({ chapter_number: 0 })
    }
  );

  eventSource.addEventListener('summary', (e) => {
    const data = JSON.parse(e.data);
    setTitle(data.title);
  });

  eventSource.addEventListener('content', (e) => {
    const data = JSON.parse(e.data);
    setContent(prev => prev + data.text);
  });

  eventSource.addEventListener('complete', (e) => {
    const data = JSON.parse(e.data);
    setOptions(data.options);
    eventSource.close();
  });
};
```

**关键点**:
- ✅ 前端不需要单独的重试接口
- ✅ 复用Phase 3的`generateChapter()`函数
- ✅ 后端自动处理failed状态

## 完整流程示例

### 场景: 第3章生成失败,用户重试

**初始状态**:
```
Chapter 1 [COMPLETED] - UserChoice(chapter=1, option=2)
Chapter 2 [COMPLETED] - UserChoice(chapter=2, option=1)
Chapter 3 [FAILED]
```

**用户操作**: 点击"重试"按钮

**执行流程**:
```
1. 前端: 调用generateChapter() (复用Phase 3函数)
   POST /novels/1/chapters/generate
   body: {chapter_number: 0}

2. 后端: 检测到Chapter 3, status=failed
   调用: handle_failed_retry()

3. Phase 4: 清理失败数据
   - 删除PostgreSQL: Chapter 3
   - 删除Redis: chapter:3:generating (如果有)

4. Phase 4: 复用Phase 3生成逻辑
   async for event in start_new_generation():
     - 查询UserChoice(chapter=2, option=1)
     - 创建新的Chapter 3
     - 启动background_generate_task
     - 返回stream_from_redis()

5. 前端: 接收SSE事件 (与首次生成完全一致)
   - summary事件: 显示title
   - content事件: 增量显示content
   - complete事件: 显示options
```

**最终状态**:
```
Chapter 1 [COMPLETED]
Chapter 2 [COMPLETED]
Chapter 3 [GENERATING/COMPLETED] (新生成的)
```

## 边界情况处理

### 1. 第一章生成失败

```python
# Phase 3的start_new_generation已经处理
if chapter_number == 1:
    # 没有UserChoice,使用小说设定生成
    novel = await novel_service.get_novel(novel_id)
    # ... 生成第一章
```

**Phase 4无需特殊处理,直接复用**

### 2. 找不到UserChoice

```python
# Phase 3的start_new_generation已经处理
if not user_choice and chapter_number > 1:
    raise HTTPException(400, "未找到用户选择记录")
```

**Phase 4无需特殊处理,直接复用**

### 3. Redis数据已不存在

```python
# Phase 4: 删除时容错处理
try:
    await ChapterCacheService.delete_generating_content(chapter_id)
except Exception:
    pass  # 忽略,可能已被清理
```

### 4. 并发重试请求

```python
# Phase 3的接口层已经处理
# 通过数据库事务保证只有一个请求成功
async with db.begin():
    chapter = await chapter_service.get_chapter_with_lock(chapter_id)
    # ...
```

**Phase 4无需特殊处理,直接复用**

## 与Phase 3的职责划分

| 功能 | Phase 3 | Phase 4 |
|------|---------|---------|
| 首次生成 | ✅ 实现 | ❌ 不涉及 |
| 断线重连 | ✅ 实现 | ❌ 不涉及 |
| 失败检测 | ❌ 不涉及 | ✅ 检测status=failed |
| 失败清理 | ❌ 不涉及 | ✅ 删除PostgreSQL+Redis |
| 重新生成 | ✅ 提供能力 | ✅ 复用Phase 3 |
| stream_from_redis | ✅ 实现 | ✅ 复用 |
| start_new_generation | ✅ 实现 | ✅ 复用 |
| background_generate_task | ✅ 实现 | ✅ 复用 |

**原则**: Phase 4不重复实现任何Phase 3已有的能力

## 新增代码清单

### 后端新增

**文件**: `app/api/v1/chapters.py`

```python
# 在generate_chapter函数中增加一个分支
if target_chapter.status == ChapterStatus.FAILED:
    return StreamingResponse(
        handle_failed_retry(...),
        media_type="text/event-stream"
    )

# 新增函数
async def handle_failed_retry(...) -> AsyncGenerator[str, None]:
    # 删除失败章节
    await chapter_service.delete_chapter(chapter_id)
    await ChapterCacheService.delete_generating_content(chapter_id)

    # 复用Phase 3
    async for event in start_new_generation(...):
        yield event
```

**代码量**: ~20行 (主要是删除逻辑)

### 前端新增

**文件**: `frontend/src/components/FailedUI.jsx`

```jsx
// 新增失败UI组件
const FailedUI = ({ onRetry }) => {
  // ... 约50行
}
```

**文件**: `frontend/src/pages/Reading/ReadingPage.jsx`

```javascript
// 增加failed状态判断
if (chapter.status === 'failed') {
  setPageState('failed');
}

// 增加失败UI渲染
if (pageState === 'failed') {
  return <FailedUI onRetry={handleRetry} />;
}
```

**代码量**: ~60行 (UI组件 + 状态判断)

## 测试用例

### 1. 基本重试流程
- 模拟第3章生成失败
- 验证前端显示失败UI
- 点击重试
- 验证Chapter 3被删除
- 验证重新生成成功

### 2. 第一章失败重试
- 第1章生成失败
- 点击重试
- 验证使用小说设定重新生成

### 3. Redis已清理的情况
- 章节状态为failed
- Redis数据已被清理
- 点击重试
- 验证不报错,正常重新生成

### 4. 并发重试
- 用户快速点击两次重试
- 验证只有一个生成任务

## 相关文件

### 后端
- `app/api/v1/chapters.py` - 增加failed分支 + handle_failed_retry函数
- `app/services/chapter.py` - 复用delete_chapter方法
- `app/services/chapter_cache.py` - 复用delete_generating_content方法

### 前端
- `frontend/src/components/FailedUI.jsx` - 新增失败UI组件
- `frontend/src/pages/Reading/ReadingPage.jsx` - 增加failed状态处理

## 实现顺序

1. ✅ **先实现Phase 3** - 搭建流式生成基础能力
2. ✅ **再实现Phase 4** - 在Phase 3基础上增加失败处理
3. ✅ Phase 4复用Phase 3的所有生成逻辑,不重复造轮子

## 总结

Phase 4是一个**轻量级的增强**:
- 新增代码 < 100行
- 核心逻辑100%复用Phase 3
- 只做必要的"失败检测和清理"
- 不影响Phase 3的任何功能
