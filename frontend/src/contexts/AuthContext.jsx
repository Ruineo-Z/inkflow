import { createContext, useContext, useState, useEffect } from 'react';
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

  // 检查认证状态
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      // 验证token有效性
      fetchUserProfile()
        .then(setUser)
        .catch(() => {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        });
    }
    setIsLoading(false);
  }, []);

  // 获取用户信息
  const fetchUserProfile = async () => {
    return ApiService.get('/auth/me');
  };

  // 登录
  const login = async (credentials) => {
    try {
      const data = await ApiService.post('/auth/login', credentials);

      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      const userInfo = await fetchUserProfile();
      setUser(userInfo);
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