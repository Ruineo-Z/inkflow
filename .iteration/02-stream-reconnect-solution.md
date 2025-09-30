# 流式接口断线重连机制 - 技术方案

**日期**: 2025-09-30
**问题编号**: 问题2
**优先级**: 高

---

## 1. 问题现状

### 当前实现
- **流式技术**: FastAPI的`StreamingResponse` + HTTP Streaming
- **前端接收**: `fetch` + `response.body.getReader()`
- **数据格式**: 模仿SSE格式（`event: xxx\ndata: xxx`）

### 核心问题
用户离开正在生成的页面后：
- HTTP连接断开
- 后端generator继续执行并保存内容到数据库
- 返回页面时无法恢复进度，只能看到静态的已保存内容
- 用户体验：无法像ChatGPT那样看到"AI正在回忆"的流式效果

---

## 2. ChatGPT的实现原理（深度分析）

### 核心机制

ChatGPT **不使用轮询**，而是：

1. **后台持续生成**: HTTP连接断开后，后端继续生成并保存到DB
2. **前端持久化**: localStorage保存已接收内容和resume_token
3. **智能重连**: 返回页面时发起新的HTTP流式请求（带resume_token）
4. **差异发送**: 后端计算内容差异，流式发送给前端
5. **打字机重播**: 前端先重播已有内容，再显示新接收内容

### 关键要素

```
┌──────────────────────────────────────────────────────────┐
│ 1. HTTP连接断开后，后端generator继续执行                 │
│ 2. 生成内容实时保存到数据库                              │
│ 3. 前端保存已接收内容和resume_token                      │
│ 4. 返回页面时，发起新的流式请求（带resume_token）        │
│ 5. 后端识别resume_token，只返回"新增的"内容             │
└──────────────────────────────────────────────────────────┘
```

---

## 3. 完整时序图

### 场景1: 正常生成流程（用户不离开）

```
用户 → 前端 → 后端 → 数据库 → AI
 │      │      │       │       │
 │ 点击生成
 ├────>│      │       │       │
 │     POST /generate  │       │
 │      ├────>│       │       │
 │      │     │ 创建chapter    │
 │      │     │ status=generating
 │      │     ├──────>│       │
 │      │     │ 启动AI生成     │
 │      │     ├───────────────>│
 │      │     │       │       │
 │      │ resume_token事件    │
 │      │<────┤       │       │
 │      │ 保存localStorage    │
 │      │     │       │   AI生成chunk1
 │      │     │       │<──────┤
 │      │     │ 保存到DB      │
 │      │     ├──────>│       │
 │      │ delta事件   │       │
 │      │<────┤       │       │
 │ 显示"好的"  │       │       │
 │<─────┤     │       │       │
 │      │     │       │   AI生成chunk2
 │      │     │       │<──────┤
 │      │ delta事件   │       │
 │      │<────┤       │       │
 │ 显示"👍"    │       │       │
 │<─────┤     │       │       │
 │      │ complete事件│       │
 │      │<────┤       │       │
 │      │ 清除localStorage    │
 │      │     │ status=completed
 │      │     ├──────>│       │
```

### 场景2: 断线重连流程（用户中途离开）

```
用户 → 前端 → 后端 → 数据库 → AI
 │      │      │       │       │
 │ 点击生成
 ├────>│      │       │       │
 │      │ POST /generate      │
 │      ├────>│       │       │
 │      │     │ 创建chapter    │
 │      │     ├──────>│       │
 │      │ resume_token        │
 │      │<────┤       │       │
 │      │ localStorage保存    │
 │      │     │       │   AI生成chunk1
 │      │     │       │<──────┤
 │      │ delta: chunk1       │
 │      │<────┤       │       │
 │ 显示"好的"  │       │       │
 │<─────┤     │       │       │
 │      │ localStorage更新    │
 │      │     │       │       │
 │ 离开页面！  │       │       │
 ├────>│ 组件卸载    │       │
 │      │ HTTP断开 ╳  │       │
 │      │     │       │   AI继续生成
 │      │     │       │<──────┤
 │      │     │ 保存chunk2    │
 │      │     ├──────>│       │
 │      │     │ (无人接收)    │
 │      │     │       │   AI继续生成
 │      │     │       │<──────┤
 │      │     │ 保存完成      │
 │      │     │ status=completed
 │      │     ├──────>│       │
 │      │     │       │       │
 │ [5分钟后]   │       │       │
 │ 返回页面    │       │       │
 ├────>│ 检测localStorage    │
 │      │ 发现未完成生成      │
 │      │ {chapterId, resumeToken, content:"好的"}
 │      │     │       │       │
 │ 重播"好的"  │       │       │
 │<─────┤ (打字机效果) │       │
 │      │     │       │       │
 │      │ POST /generate?resume_token=xxx
 │      ├────>│       │       │
 │      │     │ 解析token     │
 │      │     │ 查询DB        │
 │      │     │<──────┤       │
 │      │     │ 计算差异      │
 │      │     │ 前端已有:"好的"│
 │      │     │ DB全部:"好的👍让我们..."
 │      │     │ 差异:"👍让我们..."
 │      │     │       │       │
 │      │ delta:"👍"          │
 │      │<────┤       │       │
 │ 追加显示"👍"│       │       │
 │<─────┤     │       │       │
 │      │ delta:"让我们..."   │
 │      │<────┤       │       │
 │ 追加显示    │       │       │
 │<─────┤     │       │       │
 │      │ complete事件        │
 │      │<────┤       │       │
 │      │ 清除localStorage    │
 │ 显示完整+选项│       │       │
 │<─────┤     │       │       │
```

---

## 4. 技术架构设计（Redis + PostgreSQL混合方案）

### 架构决策：为什么使用Redis

**性能考虑**：
- AI生成时高频写入（每100-200ms一次）
- 一次生成约200次写入操作
- PostgreSQL写入延迟1-5ms，Redis仅0.1-0.5ms
- **结论**: Redis承载高频写入，PostgreSQL负责持久化，避免性能瓶颈

**架构原则**：
- ✅ 一次性做对，不遗留技术债务
- ✅ Redis作为临时缓存，PostgreSQL作为持久化存储
- ✅ 数据分层：热数据在Redis，冷数据在PostgreSQL

### 4.1 数据存储分层设计

#### PostgreSQL存储（持久化层）

**chapters表新增字段**：
- `generation_status`: VARCHAR(20) - 生成状态 ('generating', 'completed', 'failed')
- `generation_session_id`: VARCHAR(50) - 生成会话ID (UUID)
- `content_length`: INTEGER - 内容长度（用于快速判断，非强依赖）
- `completed_at`: TIMESTAMP - 完成时间

**用途**：
- 持久化存储完整章节数据
- 生成完成后的唯一数据源
- 用户查询章节列表和详情

#### Redis存储（缓存层）

**Key设计**：
```
生成中的内容: chapter:generating:{chapter_id}
生成状态:     chapter:status:{chapter_id}
```

**数据结构**：
```json
// chapter:generating:{chapter_id} (String)
{
    "chapter_id": 123,
    "session_id": "uuid",
    "title": "第一章",
    "content": "好的👍让我们...",  // 实时累积的内容
    "content_length": 150,
    "options": [],  // 生成完成才有
    "created_at": 1759197225,
    "updated_at": 1759197280
}

// chapter:status:{chapter_id} (String)
"generating" | "completed" | "failed"
```

**TTL策略**：
- 生成中：无过期时间
- 生成完成：保留1小时（防止并发读取PostgreSQL）
- 生成失败：保留10分钟

**用途**：
- 高频写入操作的缓冲
- 重连时快速读取最新内容
- 生成完成前的唯一数据源

### 4.2 数据流转设计

#### 生成阶段数据流

```
AI生成chunk
    ↓
写入Redis (高频，0.1ms)
    ↓
每5秒批量同步到PostgreSQL (低频)
    ↓
生成完成时最终写入PostgreSQL
    ↓
删除Redis中的generating数据
    ↓
在Redis中缓存完整数据1小时
```

**关键优化**：
- Redis承载99%的写入压力
- PostgreSQL每5秒批量更新一次（中间状态）
- 生成完成时写入完整数据（最终状态）
- 避免Redis数据丢失：每5秒同步确保最多丢失5秒数据

#### 重连阶段数据流

```
前端发起重连请求
    ↓
后端解析resume_token
    ↓
优先查询Redis (命中率高)
    ↓
Redis未命中则查PostgreSQL
    ↓
计算内容差异
    ↓
流式发送给前端
```

**读取优先级**：
1. Redis generating数据（生成中）
2. Redis completed缓存（刚完成）
3. PostgreSQL（已完成或Redis过期）

### 4.3 Resume Token设计

**JWT Payload结构**：
```json
{
    "chapter_id": 123,
    "session_id": "uuid",
    "novel_id": 456,
    "user_id": 789,
    "sent_length": 100,
    "iat": 1759197225,
    "exp": 1759197825
}
```

**安全性考虑**：
- 包含`user_id`防止跨用户访问
- 包含`session_id`防止跨会话重放
- 10分钟有效期（与ChatGPT一致）
- 使用JWT签名防止篡改

### 4.4 后端接口改造

#### 接口签名

```
POST /novels/{novel_id}/chapters/generate?resume_token={token}

参数：
- resume_token (可选): 用于恢复之前中断的生成
```

#### 处理逻辑

**新生成流程**：
1. 创建chapter记录，status='generating'
2. 在Redis创建generating数据
3. 生成resume_token并发送给前端
4. 流式生成内容，每个chunk写入Redis
5. 每5秒批量同步到PostgreSQL（中间状态）
6. 完成时：
   - 写入完整数据到PostgreSQL
   - 更新status='completed'
   - 删除Redis generating数据
   - 在Redis缓存完整数据1小时

**重连流程**：
1. 验证resume_token（签名、用户、有效期）
2. 优先从Redis读取内容
3. Redis未命中则从PostgreSQL读取
4. 计算差异：`new_content = current_content[sent_length:]`
5. 流式发送差异内容（分chunk模拟打字机）
6. 检查状态：
   - completed → 发送complete事件
   - generating → 继续监听或返回generating事件

### 4.5 前端改造

#### localStorage数据结构

```javascript
Key: `generating_chapter_${novelId}`

Value: {
    chapterId: 123,
    novelId: 456,
    resumeToken: "eyJhbGci...",
    content: "好的👍",
    title: "第一章",
    status: "generating",
    sentLength: 100,
    timestamp: 1759197225000
}
```

#### 页面加载逻辑

1. **检查localStorage**：是否有未完成的生成
2. **验证有效期**：超过1小时的记录清除
3. **恢复生成**：
   - 先用打字机效果重播已有内容
   - 发起重连请求（带resume_token）
   - 接收并显示新内容
4. **正常加载**：无未完成生成，正常加载章节列表

#### 内容重播机制

- 每次显示5个字符
- 30ms延迟
- 模拟流式打字机效果
- 让用户感觉AI正在"回忆"

---

## 5. 核心技术问题解答

### Q1: 为什么选择Redis + PostgreSQL而不是纯PostgreSQL？

**答**: 性能和未来扩展性考虑。

**对比分析**：
- 纯PostgreSQL：每次生成200次写入，约1秒总延迟
- Redis + PostgreSQL：200次Redis写入仅20ms，PostgreSQL仅40次写入（每5秒一次）

**长期优势**：
- 避免未来性能瓶颈需要重构
- Redis可以扩展更多功能（实时推送、排行榜等）
- 一次性做对，符合零技术债务原则

### Q2: Redis数据丢失怎么办？

**答**: 双重保障机制。

**数据安全策略**：
1. Redis每5秒同步到PostgreSQL（最多丢失5秒数据）
2. 生成完成时强制写入PostgreSQL
3. Redis故障时自动降级到PostgreSQL
4. 用户最多重新生成5秒内容（可接受）

**Redis持久化配置**：
- AOF持久化（appendonly yes）
- 每秒fsync（appendfsync everysec）
- 重启后自动恢复

### Q3: 如果generator还在执行（用户快速返回）怎么办？

**答**: Redis实时读取，无需轮询。

**处理流程**：
1. 重连时从Redis读取最新内容
2. 发送差异给前端
3. 如果状态是'generating'：
   - 返回`generating`事件
   - 前端3秒后重连
   - 再次从Redis读取最新内容
4. 循环直到完成

**优势**：
- Redis读取速度极快（0.1ms）
- 不需要复杂的消息队列
- 逻辑简单清晰

### Q4: Redis部署和运维成本如何？

**答**: 使用Docker简化部署，运维成本低。

**部署方案**：
- Docker Compose一键部署Redis
- 配置持久化到宿主机目录
- 监控Redis内存使用（设置maxmemory）
- 定期备份RDB文件

**资源需求**：
- 内存：每个生成中章节约10KB，100个并发仅1MB
- CPU：极低，Redis单线程足够
- 建议配置：512MB内存专用于Redis

### Q5: 与ChatGPT的差异是什么？

**相同点**：
- Resume Token机制 ✅
- 前端持久化 ✅
- 内容重播 ✅
- 差异发送 ✅
- 高性能缓存层 ✅

**不同点**：
- ChatGPT可能用更复杂的消息队列（Kafka等）
- InkFlow使用Redis，架构更轻量
- **结果**: 实现90-95%的ChatGPT体验，架构更简洁

---

## 6. 实施步骤（Redis + PostgreSQL方案）

### 阶段0: Redis环境部署 (0.5-1小时)

**任务**：
1. 在docker-compose.yml添加Redis服务
2. 配置Redis持久化（AOF + RDB）
3. 设置内存限制和淘汰策略
4. 添加Redis健康检查

**验收标准**：
- Redis容器正常启动
- 后端能连接Redis
- 持久化配置生效

**Docker配置参考**：
```yaml
redis:
  image: redis:7-alpine
  volumes:
    - ./data/redis:/data
  command: redis-server --appendonly yes --maxmemory 512mb
```

### 阶段1: 数据库改造 (1-2小时)

**任务**：
1. 创建Alembic migration添加新字段
2. 更新Chapter模型定义
3. 运行migration
4. 编写Redis工具类（RedisClient封装）

**验收标准**：
- PostgreSQL migration执行成功
- Redis连接池正常工作
- 现有功能不受影响

### 阶段2: 后端核心逻辑 (6-8小时)

**任务**：
1. 实现Redis数据层操作
   - 写入generating数据
   - 读取generating数据
   - 更新状态
2. 实现PostgreSQL同步逻辑（每5秒）
3. 实现resume_token生成和验证
4. 修改generate接口：
   - 新生成时写Redis
   - 定时同步PostgreSQL
   - 完成时清理Redis
5. 实现重连接口：
   - 读取Redis/PostgreSQL
   - 计算差异
   - 流式发送

**验收标准**：
- 生成时内容实时写入Redis
- 每5秒同步到PostgreSQL
- 完成时数据正确清理
- 重连时能读取最新内容

### 阶段3: 前端核心逻辑 (4-6小时)

**任务**：
1. 实现localStorage持久化
2. 实现页面加载恢复逻辑
3. 实现内容重播动画
4. 实现重连请求处理
5. 优化UI提示

**验收标准**：
- 离开返回能看到重播
- 新内容正确追加
- 用户体验流畅

### 阶段4: 容错和降级 (2-3小时)

**任务**：
1. Redis故障降级到PostgreSQL
2. 数据同步失败重试机制
3. Resume token过期处理
4. 网络异常处理

**验收标准**：
- Redis宕机时系统仍可用（降级）
- 数据最终一致性保证
- 各类异常有明确提示

### 阶段5: 测试与优化 (2-3小时)

**测试场景**：
1. 正常生成流程
2. 断线重连（各种时机）
3. Redis故障降级
4. 并发生成测试
5. 长时间运行压力测试

**性能优化**：
- Redis写入批量化
- PostgreSQL同步频率调优
- 前端重播速度优化

**总工时估算**: 16-23小时

---

## 7. 最终架构方案

### 推荐方案: Redis + PostgreSQL 混合架构

**核心要素**：
- ✅ Redis高性能缓存层
- ✅ PostgreSQL持久化存储
- ✅ 每5秒批量同步机制
- ✅ Resume Token断线重连
- ✅ 前端localStorage持久化
- ✅ 内容打字机重播
- ✅ Redis故障自动降级

**架构优势**：
- ✅ 一次性做对，零技术债务
- ✅ 高性能（99%写入在Redis）
- ✅ 高可靠（双重数据保障）
- ✅ 易扩展（未来可加更多Redis功能）
- ✅ 运维简单（Docker一键部署）

**与纯PostgreSQL方案对比**：

| 指标 | 纯PostgreSQL | Redis + PostgreSQL |
|------|-------------|-------------------|
| 写入延迟 | 1-5ms × 200次 = 200-1000ms | 0.1ms × 200次 = 20ms |
| PostgreSQL负载 | 200次/生成 | 40次/生成（降低80%）|
| 扩展性 | 受限 | 优秀 |
| 实现复杂度 | 低 | 中 |
| 运维成本 | 低 | 中（多一个Redis）|
| 技术债务 | 有（未来需重构）| 无 |

**决策理由**：
- 性能提升10倍以上
- 避免未来瓶颈重构
- 运维成本可接受（Docker简化部署）
- 符合"一次性做对"原则

---

## 8. 与ChatGPT方案对比

| 特性 | ChatGPT | InkFlow方案 | 说明 |
|------|---------|------------|------|
| Resume Token | ✅ | ✅ | JWT，10分钟有效期 |
| 状态追踪 | ✅ | ✅ | Redis + PostgreSQL双层 |
| 差异发送 | ✅ | ✅ | 计算并流式发送 |
| 前端持久化 | ✅ | ✅ | localStorage |
| 内容重播 | ✅ | ✅ | 打字机效果 |
| 高性能缓存 | ✅ | ✅ | Redis |
| 数据持久化 | ✅ | ✅ | PostgreSQL |
| 故障降级 | ✅ | ✅ | Redis故障自动切换 |

**结论**: 完全复刻ChatGPT的核心体验，架构更清晰简洁。

---

## 9. 风险评估与应对

### 技术风险

**风险1: Redis数据丢失**
- **影响**: 生成中的内容可能丢失
- **概率**: 极低（AOF + 5秒同步双重保障）
- **应对**:
  - 用户最多重新生成5秒内容
  - 提供"继续生成"功能
  - Redis重启后自动恢复

**风险2: Redis性能瓶颈**
- **影响**: 并发量大时Redis可能成为瓶颈
- **概率**: 中（并发生成 > 1000时）
- **应对**:
  - 监控Redis内存和QPS
  - 达到瓶颈时增加Redis内存或使用集群

**风险3: Redis-PostgreSQL同步延迟**
- **影响**: 用户可能看到旧数据
- **概率**: 低（5秒同步已足够快）
- **应对**:
  - 优先从Redis读取
  - 添加"刷新"按钮手动更新

**风险4: Resume Token被滥用**
- **影响**: 恶意用户频繁重连消耗资源
- **概率**: 低
- **应对**:
  - 速率限制（同一章节5秒内只能重连一次）
  - IP级别的请求限制

### 用户体验风险

**风险1: 重播速度不合适**
- **影响**: 用户体验不佳
- **应对**:
  - 默认30ms/5字符
  - 未来可添加用户自定义设置

**风险2: 网络波动导致多次重连**
- **影响**: 内容重复显示
- **应对**:
  - 前端基于content_length去重
  - 添加"重连中"状态防止重复请求

### 运维风险

**风险1: Redis运维成本**
- **影响**: 增加运维工作量
- **应对**:
  - Docker简化部署
  - 自动化监控和告警
  - 详细的运维文档

**风险2: 双存储一致性**
- **影响**: Redis和PostgreSQL数据不一致
- **应对**:
  - PostgreSQL为唯一真实数据源
  - Redis仅作缓存
  - 定期数据校验和清理

---

## 10. 后续优化方向

### 短期优化（1-2周内）
1. Redis监控仪表板（内存、QPS、命中率）
2. 添加重连次数限制和指数退避
3. 优化PostgreSQL同步频率（根据实际负载调整）
4. 详细的错误提示和用户引导

### 中期优化（1-2月内）
1. 多标签页同步（使用Redis PubSub）
2. 生成进度百分比（基于预估总长度）
3. 用户可配置重播速度
4. Redis集群支持（高并发时）

### 长期优化（3月+）
1. WebSocket替代HTTP Streaming（更好的双向通信）
2. 离线生成通知（PWA + Web Push）
3. 生成历史回放（保存Redis数据供回放）
4. 智能缓存预热（预测用户可能查看的章节）

---

## 11. 总结

### 核心架构

**Redis + PostgreSQL + JWT + localStorage**

```
前端localStorage (已接收内容)
        ↕
    Resume Token (JWT)
        ↕
Redis (生成中热数据) ← 每5秒 → PostgreSQL (持久化)
```

### 关键优势

- ✅ **高性能**: 10倍于纯PostgreSQL方案
- ✅ **零技术债务**: 一次性做对，无需未来重构
- ✅ **高可靠**: 双重数据保障（Redis + PostgreSQL）
- ✅ **易扩展**: Redis支持更多功能（实时推送、排行榜等）
- ✅ **运维友好**: Docker简化部署，监控完善
- ✅ **ChatGPT级体验**: 断线重连、内容重播、流畅体验

### 实施建议

**分阶段推进**：
1. 阶段0: Redis部署（0.5-1h）
2. 阶段1: 数据库改造（1-2h）
3. 阶段2: 后端逻辑（6-8h）
4. 阶段3: 前端逻辑（4-6h）
5. 阶段4: 容错降级（2-3h）
6. 阶段5: 测试优化（2-3h）

**总工时**: 16-23小时

**质量保证**：
- 每个阶段独立验收
- 完整的测试覆盖
- 详细的监控和告警
- 清晰的运维文档

### 最终决策

采用 **Redis + PostgreSQL 混合架构**，原因：
1. 性能优势明显（10倍提升）
2. 避免技术债务累积
3. 为未来扩展打好基础
4. 运维成本可控（Docker简化）
5. 完全复刻ChatGPT体验

**这是一次性做对的最佳选择。**