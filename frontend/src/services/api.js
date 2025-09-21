// API 基础配置和通用方法
// API地址配置：优先使用构建时环境变量，然后是运行时注入，最后是默认值
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  || (typeof window !== 'undefined' && window.__API_BASE_URL__ && window.__API_BASE_URL__ !== '__API_BASE_URL__' ? window.__API_BASE_URL__ : null)
  || `http://${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:8000/api/v1`;

class ApiService {
  static isRefreshing = false;
  static failedQueue = [];

  static getAuthToken() {
    return localStorage.getItem('access_token');
  }

  static getRefreshToken() {
    return localStorage.getItem('refresh_token');
  }

  static async refreshToken() {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${refreshToken}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: Refresh failed`);
      }

      const data = await response.json();
      
      // 更新存储的tokens
      localStorage.setItem('access_token', data.access_token);
      if (data.refresh_token) {
        localStorage.setItem('refresh_token', data.refresh_token);
      }

      return data.access_token;
    } catch (error) {
      // 刷新失败，清除所有tokens
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      throw error;
    }
  }

  static async processQueue(error, token = null) {
    this.failedQueue.forEach(({ resolve, reject }) => {
      if (error) {
        reject(error);
      } else {
        resolve(token);
      }
    });
    
    this.failedQueue = [];
  }

  static async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const token = this.getAuthToken();

    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` }),
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);

      // 处理401错误 - token过期
      if (response.status === 401 && token && !options._retry) {
        if (this.isRefreshing) {
          // 如果正在刷新，将请求加入队列
          return new Promise((resolve, reject) => {
            this.failedQueue.push({ resolve, reject });
          }).then(() => {
            // 重试原始请求
            return this.request(endpoint, { ...options, _retry: true });
          });
        }

        this.isRefreshing = true;

        try {
          const newToken = await this.refreshToken();
          this.isRefreshing = false;
          this.processQueue(null, newToken);
          
          // 重试原始请求
          return this.request(endpoint, { ...options, _retry: true });
        } catch (refreshError) {
          this.isRefreshing = false;
          this.processQueue(refreshError, null);
          
          // 刷新失败，跳转到登录页
          if (typeof window !== 'undefined') {
            window.location.href = '/login';
          }
          throw refreshError;
        }
      }

      if (!response.ok) {
        const errorData = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorData}`);
      }

      // 检查是否有内容返回
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }

      return null;
    } catch (error) {
      console.error('API请求失败:', error);
      throw error;
    }
  }

  static async get(endpoint) {
    return this.request(endpoint, { method: 'GET' });
  }

  static async post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async put(endpoint, data) {
    return this.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  static async delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }
}

// 小说相关的API
export class NovelApi {
  // 获取用户的小说列表
  static async getUserNovels() {
    return ApiService.get('/novels');
  }

  // 获取小说详情
  static async getNovelDetail(novelId) {
    return ApiService.get(`/novels/${novelId}`);
  }

  // 创建新小说
  static async createNovel(novelData) {
    return ApiService.post('/novels', novelData);
  }

  // 删除小说
  static async deleteNovel(novelId) {
    return ApiService.delete(`/novels/${novelId}`);
  }
}

// 章节相关的API
export class ChapterApi {
  // 获取小说的章节列表
  static async getNovelChapters(novelId) {
    return ApiService.get(`/novels/${novelId}/chapters`);
  }

  // 获取章节详情
  static async getChapterDetail(chapterId) {
    return ApiService.get(`/chapters/${chapterId}`);
  }

  // 生成新章节（流式，需要特殊处理）
  static async generateChapter(novelId) {
    return ApiService.post(`/novels/${novelId}/chapters/generate`, {});
  }

  // 保存用户选择
  static async saveUserChoice(chapterId, optionId) {
    return ApiService.post(`/chapters/${chapterId}/choice`, {
      option_id: optionId
    });
  }
}

export default ApiService;