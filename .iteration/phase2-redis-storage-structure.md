# Phase 2: Redis存储数据结构设计

## 设计原则

**Redis中的数据仅用于前端展示,只存储前端需要显示的字段**

## Redis Key设计

```
chapter:{chapter_id}:generating
```

**说明**:
- `chapter_id`: 章节ID(PostgreSQL主键)
- `generating`: 状态标识,表示正在生成中
- Key存在 = 生成中,Key不存在 = 已完成或未开始

## Redis Value结构

```json
{
  "title": "章节标题",
  "content": "已生成的正文内容...",
  "options": []
}
```

### 字段说明

| 字段 | 类型 | 说明 | 来源事件 | 更新时机 |
|------|------|------|----------|----------|
| `title` | string | 章节标题 | summary事件 | 生成开始时写入,后续不变 |
| `content` | string | 正文内容(纯文本) | content事件 | 流式更新,持续累加 |
| `options` | array | 章节选项列表 | complete事件 | 生成完成时写入 |

### options数组结构

```json
"options": [
  "跟随师父学艺",
  "独自下山闯荡",
  "留在山上修炼"
]
```

**说明**:
- 只存储选项文本,不存储`impact_hint`和`tags`
- 前端只需要显示选项按钮,不需要其他信息
- `impact_hint`和`tags`完整保存在PostgreSQL中,供后端生成下一章时使用

## 数据生命周期

### 1. 生成开始 (summary事件)
```json
{
  "title": "第一章:初入江湖",
  "content": "",
  "options": []
}
```

### 2. 生成中 (content事件,持续更新)
```json
{
  "title": "第一章:初入江湖",
  "content": "很久以前,在遥远的武林中...(500字)",
  "options": []
}
```

### 3. 生成完成 (complete事件)
```json
{
  "title": "第一章:初入江湖",
  "content": "很久以前,在遥远的武林中...(2500字)",
  "options": [
    "跟随师父学艺",
    "独自下山闯荡",
    "留在山上修炼"
  ]
}
```

**完成后操作**: 立即删除Redis Key (数据已写入PostgreSQL)

### 4. 生成失败
**操作**: 立即删除Redis Key (下次重试时重新创建)

## 不存储的字段

以下字段**不**存储在Redis中:

| 字段 | 原因 |
|------|------|
| `session_id` | 前端不需要,chapter_id已足够唯一标识 |
| `novel_id` | 前端已知当前小说ID,不需要存储 |
| `content_length` | 前端可自行计算`content.length` |
| `summary` | 前端不需要实时显示摘要 |
| `key_events` | 前端不需要实时显示关键事件 |
| `conflicts` | 前端不需要实时显示冲突点 |
| `status` | 通过Key的存在与否判断(存在=generating) |
| `error` | 失败后直接删除Key,不保留错误信息 |
| `impact_hint` | 选项影响提示,前端不展示 |
| `tags` | 选项标签,前端不展示 |

## TTL设置

**不设置TTL**

理由:
- 生成成功 → 主动删除
- 生成失败 → 主动删除
- 不存在"生成中但长时间无更新"的正常场景
- 如需清理僵尸数据,由后台定时任务处理(检查generating状态超过1小时的章节)

## Redis操作封装

**ChapterCacheService方法定义**:

```python
class ChapterCacheService:

    @staticmethod
    async def set_generating_content(
        chapter_id: int,
        title: str,
        content: str,
        options: list = []
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

## 前端使用示例

```javascript
// SSE接收到content事件
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (event.type === 'summary') {
    setTitle(data.title);  // 设置标题
  } else if (event.type === 'content') {
    setContent(prev => prev + data.text);  // 追加内容
  } else if (event.type === 'complete') {
    setOptions(data.options);  // 设置选项
  }
}

// 显示进度
<div>已生成: {content.length} 字</div>
```

## 数据一致性保证

**原则**: Redis是临时缓存,PostgreSQL是最终数据源

- ✅ 生成中: 前端从Redis读取
- ✅ 完成后: Redis删除,前端从PostgreSQL读取
- ✅ 失败后: Redis删除,重试时重新创建
- ✅ 断线重连: 检测Redis → 存在则继续,不存在则从PostgreSQL读取

## 相关文件

- `app/services/chapter_cache.py` - Redis操作封装
- `app/services/stream_manager.py` - 流式生成管理器
- `app/api/v1/chapters.py` - 章节生成接口
