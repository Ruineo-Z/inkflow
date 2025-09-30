import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import ApiService from '../services/api';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const refreshTimerRef = useRef(null);
  const retryCountRef = useRef(0);

  // 处理Token刷新(带重试机制)
  const handleTokenRefresh = useCallback(async () => {
    const MAX_RETRIES = 3;

    try {
      console.log('Starting token refresh...', { attempt: retryCountRef.current + 1 });
      await ApiService.refreshAccessToken();
      retryCountRef.current = 0; // 重置重试计数
      console.log('Token refresh successful, next refresh scheduled');
      setupTokenRefresh();
    } catch (error) {
      console.error(`Token refresh failed (attempt ${retryCountRef.current + 1}):`, {
        error: error.message,
        code: error.code,
        status: error.status,
        timestamp: new Date().toISOString()
      });

      // 401错误表示refresh token无效,直接登出
      if (error.code === 'INVALID_REFRESH_TOKEN' || error.status === 401) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        setUser(null);
        window.location.href = '/login';
        return;
      }

      // 网络错误或服务器错误,尝试重试
      if (retryCountRef.current < MAX_RETRIES) {
        const delay = Math.pow(2, retryCountRef.current) * 1000; // 指数退避: 1s, 2s, 4s
        console.log(`Will retry token refresh in ${delay}ms`);
        retryCountRef.current++;

        refreshTimerRef.current = setTimeout(handleTokenRefresh, delay);
        return;
      }

      // 重试次数用尽,登出用户
      console.error('Token refresh failed after max retries, logging out');
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setUser(null);
      window.location.href = '/login';
    }
  }, []);

  // 设置Token自动刷新
  const setupTokenRefresh = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }

    const token = localStorage.getItem('access_token');
    if (!token) return;

    try {
      const payload = ApiService.decodeToken(token);

      if (!payload || !payload.exp || typeof payload.exp !== 'number') {
        console.warn('Invalid token payload');
        return;
      }

      const expiresAt = payload.exp * 1000;
      const now = Date.now();

      // Token已过期
      if (expiresAt < now) {
        console.warn('Token already expired, refreshing immediately');
        handleTokenRefresh();
        return;
      }

      const refreshAt = expiresAt - 5 * 60 * 1000; // 过期前5分钟刷新
      const delay = refreshAt - now;

      // Token即将过期
      if (delay <= 0) {
        console.log('Token expiring soon, refreshing immediately');
        handleTokenRefresh();
        return;
      }

      // setTimeout最大延迟约24.8天
      const MAX_DELAY = 2147483647;
      if (delay > MAX_DELAY) {
        console.warn('Token refresh delay exceeds setTimeout limit, using fallback');
        refreshTimerRef.current = setTimeout(() => setupTokenRefresh(), MAX_DELAY);
        return;
      }

      console.log('Token refresh scheduled', {
        expiresAt: new Date(expiresAt).toISOString(),
        refreshAt: new Date(refreshAt).toISOString(),
        delayMinutes: Math.floor(delay / 1000 / 60)
      });

      refreshTimerRef.current = setTimeout(handleTokenRefresh, delay);
    } catch (error) {
      console.error('Error setting up token refresh:', error);
    }
  }, [handleTokenRefresh]);

  // 获取用户信息
  const fetchUserProfile = useCallback(async () => {
    return ApiService.get('/auth/me');
  }, []);

  // 检查认证状态
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      fetchUserProfile()
        .then(user => {
          setUser(user);
          setupTokenRefresh();
        })
        .catch((error) => {
          console.error('Failed to fetch user profile on init:', {
            error: error.message,
            status: error.status,
            timestamp: new Date().toISOString()
          });
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, [fetchUserProfile, setupTokenRefresh]);

  // 清理定时器
  useEffect(() => {
    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, []);

  // 登录
  const login = async (credentials) => {
    try {
      const data = await ApiService.post('/auth/login', credentials);

      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      const userInfo = await fetchUserProfile();
      setUser(userInfo);
      setupTokenRefresh();
      return userInfo;

    } catch (error) {
      // 处理具体的错误信息
      if (error.message.includes('HTTP 401')) {
        throw new Error('邮箱或密码错误');
      } else if (error.message.includes('HTTP 422')) {
        throw new Error('请检查邮箱格式和密码长度');
      } else if (error.message.includes('HTTP 5')) {
        throw new Error('服务器错误，请稍后重试');
      } else if (error.message.includes('Failed to fetch')) {
        throw new Error('网络连接失败，请检查网络连接');
      }
      throw error;
    }
  };

  // 注册
  const register = async (userData) => {
    try {
      const data = await ApiService.post('/auth/register', userData);

      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      const userInfo = await fetchUserProfile();
      setUser(userInfo);
      setupTokenRefresh();
      return userInfo;

    } catch (error) {
      // 处理注册错误
      if (error.message.includes('HTTP 400')) {
        throw new Error('用户名或邮箱已存在');
      } else if (error.message.includes('HTTP 422')) {
        throw new Error('请检查输入信息格式');
      }
      throw new Error(error.message || '注册失败，请稍后重试');
    }
  };

  // 登出
  const logout = async () => {
    try {
      await ApiService.post('/auth/logout', {});
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
      retryCountRef.current = 0; // 重置重试计数
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setUser(null);
    }
  };

  const value = {
    user,
    isLoading,
    login,
    register,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;