// API 基础配置和通用方法
// 运行时配置API地址，通过启动脚本注入到页面中
const API_BASE_URL = (typeof window !== 'undefined' && window.__API_BASE_URL__)
  || `http://${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:8000/api/v1`;

class ApiService {
  static getAuthToken() {
    return localStorage.getItem('access_token');
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