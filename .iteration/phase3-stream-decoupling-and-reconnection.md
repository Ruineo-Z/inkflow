# Phase 3: 流式生成解耦与断线重连

## 目标

**实现生成与HTTP连接的完全解耦**:
- 后台任务持续生成 → 实时写入Redis
- 前端随时连接/断开 → 从Redis增量获取
- 支持两种场景: 离开网页、关闭网站

## 核心设计原则

1. **前端尽量轻量** - 只负责调用接口和显示,不做复杂判断
2. **后端统一入口** - 所有生成相关操作都通过同一个接口
3. **增量推送** - 避免数据冗余,提升网络效率和用户体验
4. **接口完整性** - 统一接口处理所有章节状态,业务逻辑分离

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                         前端                                 │
│  - 调用统一生成接口                                          │
│  - 接收SSE事件,增量append显示                                │
│  - 不需要判断是首次/重连/重试                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓ SSE
┌─────────────────────────────────────────────────────────────┐
│                    统一生成接口                               │
│  POST /novels/{novel_id}/chapters/generate                  │
│  - 自动检测章节状态                                          │
│  - 路由到对应处理逻辑                                        │
└─────────────────────────────────────────────────────────────┘
           ↙          ↓          ↓          ↘
    ┌─────────┐  ┌─────────┐ ┌─────────┐ ┌─────────┐
    │首次生成 │  │断线重连 │ │失败重试 │ │已完成   │
    └─────────┘  └─────────┘ └─────────┘ └─────────┘
         ↓              ↓
    ┌─────────┐  ┌─────────┐
    │后台任务 │  │从Redis  │
    │写Redis  │  │流式读取 │
    └─────────┘  └─────────┘
         ↓              ↓
    ┌──────────────────────────┐
    │         Redis            │
    │  chapter:X:generating    │
    │  {title, content, opts}  │
    └──────────────────────────┘
```

## 数据流详解

### 1. 后台生成流程 (解耦)

```python
# background_generate_task
async def background_generate_task(chapter_id, novel_id, ...):
    async for stream_chunk in chapter_generator.generate_xxx_stream(...):

        if stream_chunk.event == 'summary':
            # 写入title到Redis
            await ChapterCacheService.set_generating_content(
                chapter_id=chapter_id,
                title=stream_chunk.data['title'],
                content="",
                options=[]
            )

        elif stream_chunk.event == 'content':
            # 提取content并累加到Redis
            accumulated_json = stream_chunk.data['accumulated']
            pure_content = extract_content_from_json_fragment(accumulated_json)

            await ChapterCacheService.set_generating_content(
                chapter_id=chapter_id,
                title=current_title,  # 保持不变
                content=pure_content,  # 更新content
                options=[]
            )

        elif stream_chunk.event == 'complete':
            # 写入PostgreSQL + 删除Redis
            await chapter_service.update_chapter(...)
            await ChapterCacheService.delete_generating_content(chapter_id)
```

**关键点**:
- ✅ 不依赖HTTP连接,独立运行
- ✅ 实时写入Redis,前端随时可读
- ✅ 完成后删除Redis,数据进入PostgreSQL

### 2. 前端重连流程 (轻量)

```javascript
// 前端只需要一个函数
const generateChapter = async () => {
  const eventSource = new EventSource(
    `/api/v1/novels/${novelId}/chapters/generate`,
    {
      method: 'POST',
      body: JSON.stringify({ chapter_number: 0 })
    }
  );

  // 接收title
  eventSource.addEventListener('summary', (e) => {
    const data = JSON.parse(e.data);
    setTitle(data.title);
  });

  // 接收增量content
  eventSource.addEventListener('content', (e) => {
    const data = JSON.parse(e.data);
    setContent(prev => prev + data.text);  // 增量append
  });

  // 接收完成事件
  eventSource.addEventListener('complete', (e) => {
    const data = JSON.parse(e.data);
    setOptions(data.options);
    eventSource.close();
  });
};
```

**关键点**:
- ✅ 不需要判断是首次/重连/重试
- ✅ 统一接口,后端自动处理
- ✅ 增量append,用户体验流畅

### 3. 后端统一接口实现

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
    自动处理: 首次生成/断线重连/失败重试/已完成
    """
    chapter_number = request.chapter_number

    # 1. chapter_number=0 表示最新章节
    if chapter_number == 0:
        latest_chapter = await chapter_service.get_latest_chapter(novel_id)
        if latest_chapter:
            target_chapter = latest_chapter
        else:
            # 第一章
            chapter_number = 1
            target_chapter = None
    else:
        target_chapter = await chapter_service.get_chapter_by_number(
            novel_id, chapter_number
        )

    # 2. 根据章节状态路由
    if target_chapter:
        if target_chapter.status == ChapterStatus.GENERATING:
            # 场景: 断线重连
            return StreamingResponse(
                stream_from_redis(target_chapter.id),
                media_type="text/event-stream"
            )

        elif target_chapter.status == ChapterStatus.FAILED:
            # 场景: 失败重试 (业务逻辑由Phase 4提供)
            return StreamingResponse(
                handle_failed_retry(target_chapter, novel_id, current_user_id, db),
                media_type="text/event-stream"
            )

        elif target_chapter.status == ChapterStatus.COMPLETED:
            # 场景: 已完成,返回错误
            raise HTTPException(400, "章节已生成完成")

    # 3. 场景: 首次生成
    return StreamingResponse(
        handle_new_generation(novel_id, chapter_number, db),
        media_type="text/event-stream"
    )
```

### 4. 从Redis流式读取实现 (增量推送)

```python
async def stream_from_redis(chapter_id: int) -> AsyncGenerator[str, None]:
    """
    从Redis流式读取生成中的内容
    采用增量推送策略,避免数据冗余
    """
    last_sent_length = 0
    title_sent = False
    poll_interval = 0.5  # 轮询间隔500ms
    max_wait_time = 600  # 最长等待10分钟
    start_time = asyncio.get_event_loop().time()

    while True:
        # 检查超时
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > max_wait_time:
            yield f"event: error\ndata: {json.dumps({'error': '生成超时'})}\n\n"
            break

        # 从Redis读取当前数据
        data = await ChapterCacheService.get_generating_content(chapter_id)

        if not data:
            # Redis数据不存在,可能已完成
            # 尝试从PostgreSQL读取
            chapter = await chapter_service.get_chapter(chapter_id)
            if chapter and chapter.status == ChapterStatus.COMPLETED:
                # 已完成,发送complete事件
                yield f"event: complete\ndata: {json.dumps({
                    'title': chapter.title,
                    'content': chapter.content,
                    'options': [opt.option_text for opt in chapter.options]
                })}\n\n"
            else:
                # 数据丢失
                yield f"event: error\ndata: {json.dumps({'error': 'Redis数据不存在'})}\n\n"
            break

        # 发送title (只发送一次)
        if not title_sent:
            yield f"event: summary\ndata: {json.dumps({'title': data['title']})}\n\n"
            title_sent = True

        # 发送增量content
        current_content = data['content']
        current_length = len(current_content)

        if current_length > last_sent_length:
            # 计算新增部分
            new_content = current_content[last_sent_length:]
            yield f"event: content\ndata: {json.dumps({'text': new_content})}\n\n"
            last_sent_length = current_length

        # 检查是否完成
        if data.get('options') and len(data['options']) > 0:
            # options有值,说明生成完成
            yield f"event: complete\ndata: {json.dumps({
                'title': data['title'],
                'content': data['content'],
                'options': data['options']
            })}\n\n"
            break

        # 等待下次轮询
        await asyncio.sleep(poll_interval)
```

**关键设计**:
- ✅ **增量推送**: 只发送`current_content[last_sent_length:]`
- ✅ **避免重复**: 记录`last_sent_length`,不重复发送
- ✅ **网络高效**: 2000字章节,不会反复传输前面内容
- ✅ **体验流畅**: 前端直接append,像打字机效果

### 5. content提取辅助函数

```python
import re
import json

def extract_content_from_json_fragment(json_str: str) -> str:
    """
    从可能不完整的JSON片段中提取content字段

    Kimi返回: '{"title":"...", "content":"第一段文字...'
    提取结果: "第一段文字..."
    """
    # 方法1: 尝试完整JSON解析
    try:
        parsed = json.loads(json_str)
        return parsed.get('content', '')
    except json.JSONDecodeError:
        pass

    # 方法2: 正则提取 (处理不完整JSON)
    match = re.search(
        r'"content"\s*:\s*"((?:[^"\\]|\\.)*)',
        json_str,
        re.DOTALL
    )

    if match:
        content = match.group(1)

        # 处理JSON转义字符
        content = content.replace('\\n', '\n')
        content = content.replace('\\t', '\t')
        content = content.replace('\\"', '"')
        content = content.replace('\\\\', '\\')

        return content

    # 未找到content字段
    return ""
```

## content事件传递优化

### 当前问题
chapter_generator只传递了`chunk`,丢弃了`accumulated`:

```python
# chapter_generator.py 第283行
chunk_text = stream_chunk.data['chunk']  # 只用了chunk
yield f"event: content\ndata: {json_dumps_chinese({'text': chunk_text})}\n\n"
```

### 优化方案

**修改chapter_generator,同时传递chunk和accumulated**:

```python
# chapter_generator.py 第280-283行
if stream_chunk.chunk_type == "content":
    yield f"event: content\ndata: {json_dumps_chinese({
        'chunk': stream_chunk.data['chunk'],        # 前端显示用(可选)
        'accumulated': stream_chunk.data['accumulated']  # 后端提取用
    })}\n\n"
```

**background_generate_task使用accumulated**:

```python
elif event_type == "content":
    event_data = json.loads(data_line.split('data: ')[1])

    # 使用accumulated进行content提取
    accumulated_json = event_data['accumulated']
    pure_content = extract_content_from_json_fragment(accumulated_json)

    # 写入Redis
    await ChapterCacheService.set_generating_content(
        chapter_id=chapter_id,
        title=current_title,
        content=pure_content,
        options=[]
    )
```

## 使用场景示例

### 场景1: 首次生成第一章

**前端**:
```javascript
// 进入阅读页面
useEffect(() => {
  generateChapter();  // 直接调用
}, []);
```

**后端**:
```
1. 接收: POST /generate, chapter_number=0
2. 查询: 没有章节
3. 判断: 首次生成第一章
4. 创建: Chapter 1, status=generating
5. 启动: background_generate_task (写Redis)
6. 返回: stream_from_redis (读Redis增量推送)
```

### 场景2: 生成中离开页面

**用户操作**: 第2章生成到500字时,切换到其他标签页

**后台**: background_generate_task继续运行,写Redis到2000字完成

**用户返回**:
```javascript
useEffect(() => {
  generateChapter();  // 同样的调用
}, []);
```

**后端**:
```
1. 接收: POST /generate, chapter_number=0
2. 查询: Chapter 2, status=generating
3. 判断: 断线重连
4. 返回: stream_from_redis
   - 发送title: "第二章"
   - 发送content: 2000字完整内容 (增量推送)
   - 发送complete: options
```

**前端显示**: 平滑显示2000字,像打字机效果

### 场景3: 关闭浏览器后重新打开

**用户操作**: 第3章生成中,关闭浏览器

**后台**: background_generate_task继续完成生成

**用户重新打开**:
```javascript
// 前端判断逻辑
const chapter = await fetchLatestChapter();
if (chapter.status === 'completed') {
  displayChapter(chapter);  // 从PostgreSQL读取显示
}
```

### 场景4: 生成失败后重试

**用户操作**: 第4章生成失败,点击"重试"

**前端**:
```javascript
const handleRetry = () => {
  generateChapter();  // 同样的调用
}
```

**后端**:
```
1. 接收: POST /generate, chapter_number=0
2. 查询: Chapter 4, status=failed
3. 判断: 失败重试
4. 删除: Chapter 4 + Redis数据
5. 查询: UserChoice(chapter=3, option=2)
6. 创建: 新的Chapter 4
7. 启动: background_generate_task
8. 返回: stream_from_redis
```

## Redis操作封装更新

```python
class ChapterCacheService:

    @staticmethod
    async def set_generating_content(
        chapter_id: int,
        title: str,
        content: str,
        options: List[str] = []
    ) -> None:
        """设置生成中的章节内容"""
        key = f"chapter:{chapter_id}:generating"
        value = {
            "title": title,
            "content": content,
            "options": options
        }
        await redis.set(key, json.dumps(value, ensure_ascii=False))

    @staticmethod
    async def get_generating_content(chapter_id: int) -> Optional[dict]:
        """获取生成中的章节内容"""
        key = f"chapter:{chapter_id}:generating"
        data = await redis.get(key)
        if data:
            return json.loads(data)
        return None

    @staticmethod
    async def delete_generating_content(chapter_id: int) -> None:
        """删除生成中的章节内容"""
        key = f"chapter:{chapter_id}:generating"
        await redis.delete(key)
```

## 前端完整实现

```javascript
const ReadingPage = () => {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [options, setOptions] = useState([]);
  const [status, setStatus] = useState('loading');

  useEffect(() => {
    generateChapter();
  }, []);

  const generateChapter = async () => {
    try {
      setStatus('generating');

      const eventSource = new EventSource(
        `/api/v1/novels/${novelId}/chapters/generate`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ chapter_number: 0 })
        }
      );

      eventSource.addEventListener('summary', (e) => {
        const data = JSON.parse(e.data);
        setTitle(data.title);
      });

      eventSource.addEventListener('content', (e) => {
        const data = JSON.parse(e.data);
        setContent(prev => prev + data.text);  // 增量append
      });

      eventSource.addEventListener('complete', (e) => {
        const data = JSON.parse(e.data);
        setOptions(data.options);
        setStatus('completed');
        eventSource.close();
      });

      eventSource.addEventListener('error', (e) => {
        console.error('SSE error:', e);
        setStatus('failed');
        eventSource.close();
      });

    } catch (error) {
      console.error('生成失败:', error);
      setStatus('failed');
    }
  };

  return (
    <div>
      <h1>{title}</h1>
      <div className="content">{content}</div>
      {status === 'generating' && <Loading text={`已生成 ${content.length} 字`} />}
      {status === 'completed' && (
        <div className="options">
          {options.map((opt, idx) => (
            <Button key={idx} onClick={() => handleChoice(idx)}>
              {opt}
            </Button>
          ))}
        </div>
      )}
      {status === 'failed' && (
        <Button onClick={generateChapter}>重试</Button>
      )}
    </div>
  );
};
```

## 边界情况处理

### 1. Redis数据丢失
```python
# stream_from_redis中
if not data:
    # 尝试从PostgreSQL读取
    chapter = await chapter_service.get_chapter(chapter_id)
    if chapter and chapter.status == ChapterStatus.COMPLETED:
        yield complete_event
    else:
        yield error_event
```

### 2. 生成超时
```python
max_wait_time = 600  # 10分钟
if elapsed > max_wait_time:
    yield f"event: error\ndata: {json.dumps({'error': '生成超时'})}\n\n"
    # 标记章节为failed
    await chapter_service.update_status(chapter_id, ChapterStatus.FAILED)
```

### 3. 并发生成请求
```python
# 使用数据库锁
async with db.begin():
    chapter = await chapter_service.get_chapter_with_lock(chapter_id)
    if chapter.status == ChapterStatus.GENERATING:
        # 已有生成任务,直接返回Redis流
        return stream_from_redis(chapter_id)
```

## 性能优化

### 1. Redis轮询优化
```python
# 自适应轮询间隔
if no_change_count > 5:
    poll_interval = 1.0  # 长时间无变化,降低频率
else:
    poll_interval = 0.5  # 有变化,保持高频
```

### 2. 前端显示优化
```javascript
// 使用虚拟滚动处理长文本
import { FixedSizeList } from 'react-window';

// 分段渲染,避免一次性渲染2000字卡顿
const renderContent = () => {
  const paragraphs = content.split('\n');
  return paragraphs.map((p, i) => <p key={i}>{p}</p>);
}
```

## 相关文件

### 后端
- `app/api/v1/chapters.py` - 统一生成接口,stream_from_redis
- `app/services/chapter_generator.py` - 修改content事件传递
- `app/services/chapter_cache.py` - Redis操作封装
- `app/utils/content_extractor.py` - content提取辅助函数(新增)

### 前端
- `frontend/src/pages/Reading/ReadingPage.jsx` - 阅读页面
- `frontend/src/services/api.js` - API调用封装

## 测试验证

### 1. 首次生成测试
- 打开阅读页面
- 验证流式显示
- 验证打字机效果

### 2. 断线重连测试
- 生成到一半刷新页面
- 验证内容不丢失
- 验证从断点继续

### 3. 关闭浏览器测试
- 生成中关闭浏览器
- 等待后台完成
- 重新打开,验证显示完整章节

### 4. 失败重试测试
- 模拟生成失败
- 点击重试
- 验证基于UserChoice重新生成

### 5. 增量推送测试
- 监控网络请求
- 验证没有重复传输
- 验证只推送增量部分

## 与Phase 4的关系

**Phase 3职责**: 提供完整的统一生成接口
- 实现接口路由逻辑,处理所有章节状态
- 实现`stream_from_redis()` - 从Redis流式读取
- 实现`start_new_generation()` - 首次生成逻辑
- 实现`background_generate_task()` - 后台生成任务
- **调用**`handle_failed_retry()` - 失败重试逻辑(由Phase 4提供)

**Phase 4职责**: 提供失败重试业务逻辑
- 实现`handle_failed_retry()`函数 - 清理失败数据,复用Phase 3生成能力
- 实现`FailedUI`组件 - 失败状态UI
- **不修改**Phase 3的接口代码

**职责划分**:
- Phase 3负责"接口完整性" - 统一入口,状态路由
- Phase 4负责"业务逻辑" - 失败处理的具体实现
- 保持接口简洁,业务逻辑分离
