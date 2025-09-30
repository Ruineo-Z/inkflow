# Token自动刷新机制 - 技术方案

**日期**: 2025-09-30
**问题编号**: 问题1
**优先级**: 高

---

## 1. 现状分析

### 后端实现（✅ 已完成）
- **Access Token过期时间**: 30分钟 (`app/core/security.py:23`)
- **Refresh Token过期时间**: 7天 (`app/core/security.py:32`)
- **Refresh接口**: `/api/v1/auth/refresh` 已实现 (`app/api/v1/auth.py:53-68`)
- **Token生成逻辑**:
  - `create_access_token()` - 生成访问令牌
  - `create_refresh_token()` - 生成刷新令牌，带 `type: "refresh"` 标识

### 前端现状（❌ 缺失功能）
- **Token存储**:
  - `localStorage.setItem('access_token')` - Access Token已存储
  - `localStorage.setItem('refresh_token')` - Refresh Token已存储但未使用
- **缺失功能**:
  - 无自动刷新逻辑
  - 无Token过期检测
  - 无刷新失败处理

### 用户体验影响
- **当前问题**: 用户使用超过30分钟后，API请求会突然返回401错误
- **用户感知**: 操作中断，需要重新登录，体验较差
- **典型场景**:
  - 长时间阅读小说章节
  - 反复进行选择和生成
  - 页面保持打开但未操作

---

## 2. 技术方案设计

### 2.1 刷新策略

**主动刷新策略 - 提前5分钟刷新**

- **触发时机**: Token过期前5分钟自动刷新
- **实现方式**:
  1. 登录/注册时解析Token获取过期时间 (`exp` claim)
  2. 启动定时器在过期前5分钟触发刷新
  3. 刷新成功后重新设置定时器

**优点**:
- 用户完全无感知
- 避免请求中断
- 逻辑简单清晰

**缺点**:
- 依赖客户端时钟准确性
- 需要额外的Token解析逻辑

### 2.2 刷新失败处理

**Refresh Token过期处理**:
- **策略**: 静默跳转到登录页
- **实现**:
  1. 刷新失败时清除所有本地Token
  2. 使用 `react-router` 导航到登录页
  3. 不显示错误提示（静默处理）

**原因**:
- Refresh Token有效期7天，过期说明用户长时间未使用
- 静默跳转避免打扰用户
- 符合大多数Web应用的行为模式

---

## 3. 实施计划

### 3.1 前端实现

#### 步骤1: 扩展 `api.js` - 添加Token刷新方法

**位置**: `frontend/src/services/api.js`

```javascript
class ApiService {
  // 现有方法...

  static getRefreshToken() {
    return localStorage.getItem('refresh_token');
  }

  static async refreshAccessToken() {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      throw new Error('Failed to refresh token');
    }

    const data = await response.json();
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);

    return data;
  }

  static decodeToken(token) {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error('Token decode error:', error);
      return null;
    }
  }
}
```

#### 步骤2: 增强 `AuthContext.jsx` - 添加自动刷新逻辑

**位置**: `frontend/src/contexts/AuthContext.jsx`

```javascript
import { useNavigate } from 'react-router-dom';

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshTimer, setRefreshTimer] = useState(null);
  const navigate = useNavigate();

  // 设置Token自动刷新
  const setupTokenRefresh = () => {
    // 清除现有定时器
    if (refreshTimer) {
      clearTimeout(refreshTimer);
    }

    const token = localStorage.getItem('access_token');
    if (!token) return;

    const payload = ApiService.decodeToken(token);
    if (!payload || !payload.exp) return;

    // 计算刷新时机: 过期时间 - 5分钟 - 当前时间
    const expiresAt = payload.exp * 1000; // 转换为毫秒
    const refreshAt = expiresAt - 5 * 60 * 1000; // 提前5分钟
    const now = Date.now();
    const delay = refreshAt - now;

    // 如果已经过了刷新时间，立即刷新
    if (delay <= 0) {
      handleTokenRefresh();
      return;
    }

    // 设置定时器
    const timer = setTimeout(handleTokenRefresh, delay);
    setRefreshTimer(timer);
  };

  // 处理Token刷新
  const handleTokenRefresh = async () => {
    try {
      await ApiService.refreshAccessToken();
      // 刷新成功后重新设置定时器
      setupTokenRefresh();
    } catch (error) {
      console.error('Token refresh failed:', error);
      // 刷新失败，清除Token并跳转登录页
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setUser(null);
      navigate('/login', { replace: true });
    }
  };

  // 检查认证状态
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      fetchUserProfile()
        .then(user => {
          setUser(user);
          setupTokenRefresh(); // 启动自动刷新
        })
        .catch(() => {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        });
    }
    setIsLoading(false);
  }, []);

  // 清理定时器
  useEffect(() => {
    return () => {
      if (refreshTimer) {
        clearTimeout(refreshTimer);
      }
    };
  }, [refreshTimer]);

  // 登录成功后启动刷新
  const login = async (credentials) => {
    try {
      const data = await ApiService.post('/auth/login', credentials);
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      const userInfo = await fetchUserProfile();
      setUser(userInfo);
      setupTokenRefresh(); // 启动自动刷新
      return userInfo;
    } catch (error) {
      // 错误处理...
    }
  };

  // 注册成功后启动刷新
  const register = async (userData) => {
    try {
      const data = await ApiService.post('/auth/register', userData);
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      const userInfo = await fetchUserProfile();
      setUser(userInfo);
      setupTokenRefresh(); // 启动自动刷新
      return userInfo;
    } catch (error) {
      // 错误处理...
    }
  };

  // 登出时清除定时器
  const logout = async () => {
    try {
      await ApiService.post('/auth/logout', {});
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      if (refreshTimer) {
        clearTimeout(refreshTimer);
        setRefreshTimer(null);
      }
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setUser(null);
    }
  };

  // ...其余代码
};
```

### 3.2 测试计划

#### 单元测试
- [ ] Token解码函数测试
- [ ] 刷新API调用测试
- [ ] 定时器设置逻辑测试

#### 集成测试
- [ ] 登录后自动刷新流程
- [ ] Token过期前5分钟触发刷新
- [ ] Refresh Token过期后跳转登录

#### 手动测试场景
1. **正常刷新流程**:
   - 登录后等待25分钟
   - 验证Token自动刷新
   - 验证API请求正常

2. **Refresh Token过期**:
   - 手动修改localStorage中的refresh_token为无效值
   - 等待刷新触发
   - 验证是否静默跳转到登录页

3. **多标签页同步**:
   - 打开多个标签页
   - 验证Token刷新是否在所有标签页生效

---

## 4. 质量标准

### 代码质量
- ✅ 无TODO/FIXME标记
- ✅ 错误必须向上抛出，不静默失败
- ✅ 变量命名准确反映用途
- ✅ 函数职责单一明确

### 功能标准
- ✅ Token在过期前5分钟自动刷新
- ✅ 刷新失败时静默跳转登录页
- ✅ 不影响现有功能
- ✅ 用户无感知切换

### 性能标准
- ✅ 定时器资源正确释放
- ✅ 不造成内存泄漏
- ✅ Token解码性能无问题

---

## 5. 潜在风险与应对

### 风险1: 客户端时钟不准确
- **影响**: 刷新时机计算错误
- **应对**: 添加API请求401兜底机制（后续优化）

### 风险2: 多标签页Token不同步
- **影响**: 某个标签页刷新后其他标签页仍使用旧Token
- **应对**: 使用 `storage` 事件监听localStorage变化（后续优化）

### 风险3: 刷新请求失败
- **影响**: 用户被强制登出
- **应对**: 已实现静默跳转，7天有效期足够长

---

## 6. 后续优化方向

1. **添加401兜底机制**: API请求返回401时尝试刷新Token后重试
2. **多标签页同步**: 监听localStorage变化，同步Token状态
3. **刷新失败重试**: 网络临时故障时增加重试逻辑
4. **用户提示优化**: 长时间无操作后提示即将登出

---

## 7. 参考资料

- JWT最佳实践: https://tools.ietf.org/html/rfc7519
- React定时器管理: https://react.dev/learn/synchronizing-with-effects
- Token刷新策略: https://auth0.com/blog/refresh-tokens-what-are-they-and-when-to-use-them/