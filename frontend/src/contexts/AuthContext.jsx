import { createContext, useContext, useState, useEffect } from 'react';

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
    const token = localStorage.getItem('access_token');
    const response = await fetch('/api/v1/auth/me', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch user profile');
    }

    return response.json();
  };

  // 登录
  const login = async (credentials) => {
    let response;

    try {
      response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials),
      });

      if (!response.ok) {
        const error = await response.json();

        // 根据HTTP状态码提供更具体的错误信息
        if (response.status === 401) {
          throw new Error(error.detail || 'Incorrect email or password');
        } else if (response.status === 422) {
          throw new Error('请检查邮箱格式和密码长度');
        } else if (response.status >= 500) {
          throw new Error('服务器错误，请稍后重试');
        } else {
          throw new Error(error.detail || 'Login failed');
        }
      }

      const data = await response.json();

      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      const userInfo = await fetchUserProfile();
      setUser(userInfo);
      return userInfo;

    } catch (fetchError) {
      // 网络错误处理
      if (fetchError instanceof TypeError) {
        throw new Error('网络连接失败，请检查网络连接');
      }
      throw fetchError;
    }
  };

  // 注册
  const register = async (userData) => {
    const response = await fetch('/api/v1/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(userData),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Registration failed');
    }

    const data = await response.json();

    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);

    const userInfo = await fetchUserProfile();
    setUser(userInfo);
    return userInfo;
  };

  // 登出
  const logout = async () => {
    try {
      const token = localStorage.getItem('access_token');
      await fetch('/api/v1/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
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