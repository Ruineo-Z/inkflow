// API 基础配置和通用方法
// API地址配置：优先使用构建时环境变量，然后是运行时注入，最后是默认值
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  || (typeof window !== 'undefined' && window.__API_BASE_URL__ && window.__API_BASE_URL__ !== '__API_BASE_URL__' ? window.__API_BASE_URL__ : null)
  || `http://${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:8000/api/v1`;

class ApiService {
  static getAuthToken() {
    return localStorage.getItem('access_token');
  }

  static getRefreshToken() {
    return localStorage.getItem('refresh_token');
  }

  static async refreshAccessToken() {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      const error = new Error('No refresh token available');
      error.code = 'NO_REFRESH_TOKEN';
      throw error;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const error = new Error(errorData.detail || 'Failed to refresh token');
        error.status = response.status;
        error.code = response.status === 401 ? 'INVALID_REFRESH_TOKEN' : 'REFRESH_FAILED';

        console.error('Token refresh failed:', {
          status: response.status,
          error: error.message,
          timestamp: new Date().toISOString()
        });

        throw error;
      }

      const data = await response.json();
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      console.log('Token refreshed successfully at', new Date().toISOString());
      return data;

    } catch (error) {
      // 网络错误
      if (error instanceof TypeError && error.message.includes('fetch')) {
        error.code = 'NETWORK_ERROR';
        console.error('Network error during token refresh:', error);
      }
      throw error;
    }
  }

  static decodeToken(token) {
    if (!token || typeof token !== 'string') {
      throw new Error('Invalid token: must be a non-empty string');
    }

    const parts = token.split('.');
    if (parts.length !== 3) {
      throw new Error('Invalid token format: expected 3 parts');
    }

    try {
      const base64Url = parts[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error('Token decode failed:', {
        error: error.message,
        tokenPreview: token.substring(0, 20) + '...'
      });
      throw new Error(`Failed to decode token: ${error.message}`);
    }
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