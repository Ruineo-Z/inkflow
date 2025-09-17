import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { NovelApi, ChapterApi } from '../../services/api';
import '../../styles/NovelListPage.css';

const NovelListPage = () => {
  const navigate = useNavigate();
  const [novels, setNovels] = useState([]);
  const [novelsWithChapters, setNovelsWithChapters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionSheetVisible, setActionSheetVisible] = useState(false);
  const [selectedNovel, setSelectedNovel] = useState(null);

  useEffect(() => {
    const loadNovels = async () => {
      setLoading(true);
      try {
        console.log('正在加载小说列表...');

        // 1. 获取小说列表
        const novelsData = await NovelApi.getUserNovels();
        console.log('小说列表:', novelsData);
        setNovels(novelsData);

        // 2. 为每个小说获取章节信息以计算进度
        const novelsWithProgress = await Promise.all(
          novelsData.map(async (novel) => {
            try {
              const chapters = await ChapterApi.getNovelChapters(novel.id);
              const chaptersCount = chapters.length;
              const lastReadChapter = chaptersCount; // 暂时假设读完了所有章节

              return {
                ...novel,
                chaptersCount,
                lastReadChapter,
                lastReadTime: formatLastReadTime(novel.updated_at || novel.created_at),
                status: chaptersCount > 0 ? '进行中' : '未开始',
                coverImage: getCoverImageByTitle(novel.title),
                description: extractDescriptionFromWorldSetting(novel.world_setting)
              };
            } catch (error) {
              console.warn(`获取小说 ${novel.id} 的章节信息失败:`, error);
              return {
                ...novel,
                chaptersCount: 0,
                lastReadChapter: 0,
                lastReadTime: formatLastReadTime(novel.created_at),
                status: '未开始',
                coverImage: getCoverImageByTitle(novel.title),
                description: extractDescriptionFromWorldSetting(novel.world_setting)
              };
            }
          })
        );

        setNovelsWithChapters(novelsWithProgress);
        console.log('带进度的小说列表:', novelsWithProgress);

      } catch (error) {
        console.error('加载小说列表失败:', error);
        showToast('加载失败，请重试');
      } finally {
        setLoading(false);
      }
    };

    loadNovels();
  }, []);

  // 根据标题生成封面图标
  const getCoverImageByTitle = (title) => {
    if (title.includes('武侠') || title.includes('江湖') || title.includes('剑')) return '⚔️';
    if (title.includes('科幻') || title.includes('太空') || title.includes('星际')) return '🚀';
    if (title.includes('魔法') || title.includes('法师') || title.includes('魔')) return '🔮';
    if (title.includes('冒险') || title.includes('探索')) return '🏰';
    return '📚';
  };

  // 从世界设定中提取描述
  const extractDescriptionFromWorldSetting = (worldSetting) => {
    if (!worldSetting) return '一个精彩的故事等待开始...';

    // 提取背景部分作为描述
    const backgroundMatch = worldSetting.match(/背景：([^\n]+)/);
    if (backgroundMatch) {
      return backgroundMatch[1].substring(0, 50) + '...';
    }

    return worldSetting.substring(0, 50) + '...';
  };

  // 格式化最后阅读时间
  const formatLastReadTime = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor(diffMs / (1000 * 60));

    if (diffDays > 0) {
      return `${diffDays}天前`;
    } else if (diffHours > 0) {
      return `${diffHours}小时前`;
    } else if (diffMinutes > 0) {
      return `${diffMinutes}分钟前`;
    } else {
      return '刚刚';
    }
  };

  const showToast = (message) => {
    // 简单的toast实现
    const toast = document.createElement('div');
    toast.className = 'custom-toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
      document.body.removeChild(toast);
    }, 3000);
  };

  const handleNovelAction = (novel) => {
    setSelectedNovel(novel);
    setActionSheetVisible(true);
  };

  const handleContinueReading = (novel) => {
    navigate(`/novels/${novel.id}`);
  };

  const handleEditNovel = (novel) => {
    showToast('编辑功能开发中...');
    setActionSheetVisible(false);
  };

  const handleDeleteNovel = async (novel) => {
    try {
      showToast('正在删除小说...');
      setActionSheetVisible(false);

      await NovelApi.deleteNovel(novel.id);

      // 从列表中移除已删除的小说
      setNovelsWithChapters(prev => prev.filter(n => n.id !== novel.id));
      showToast('小说删除成功');
    } catch (error) {
      console.error('删除小说失败:', error);
      showToast('删除失败，请重试');
    }
  };

  const getProgressPercentage = (novel) => {
    if (novel.chaptersCount === 0) return 0;
    return Math.round((novel.lastReadChapter / novel.chaptersCount) * 100);
  };

  const getStatusColor = (status) => {
    switch (status) {
      case '已完成': return '#52c41a';
      case '进行中': return '#1890ff';
      default: return '#666';
    }
  };

  if (loading) {
    return (
      <div className="novel-list-page">
        <nav className="custom-navbar">
          <button
            className="nav-back-btn"
            onClick={() => navigate('/home')}
          >
            ←
          </button>
          <h1>我的小说</h1>
        </nav>
        <div className="loading-container">
          <div className="loading-spinner">📚</div>
          <p>加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="novel-list-page">
      <nav className="custom-navbar">
        <button
          className="nav-back-btn"
          onClick={() => navigate('/home')}
        >
          ←
        </button>
        <h1>我的小说</h1>
      </nav>

      <div className="novel-list-content">
        {novelsWithChapters.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📖</div>
            <p className="empty-text">还没有创建任何小说</p>
            <button
              className="create-first-novel-btn"
              onClick={() => navigate('/create')}
            >
              创建第一部小说
            </button>
          </div>
        ) : (
          <>
            <div className="novels-grid">
              {novelsWithChapters.map((novel) => (
                <div
                  key={novel.id}
                  className="novel-card"
                  onClick={() => handleContinueReading(novel)}
                >
                  <div className="novel-card-header">
                    <div className="novel-cover">{novel.coverImage}</div>
                    <div className="novel-info">
                      <h3 className="novel-title">{novel.title}</h3>
                      <p className="novel-description">{novel.description}</p>
                      <div className="novel-stats">
                        <span
                          className="novel-status"
                          style={{ color: getStatusColor(novel.status) }}
                        >
                          {novel.status}
                        </span>
                        <span className="novel-chapters">
                          {novel.chaptersCount} 章节
                        </span>
                      </div>
                    </div>
                    <div
                      className="novel-actions"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleNovelAction(novel);
                      }}
                    >
                      ⋮
                    </div>
                  </div>

                  <div className="novel-progress">
                    <div className="progress-info">
                      <span>阅读进度</span>
                      <span>{getProgressPercentage(novel)}%</span>
                    </div>
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{ width: `${getProgressPercentage(novel)}%` }}
                      ></div>
                    </div>
                    <div className="last-read">
                      <span>最后阅读：{novel.lastReadTime}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <button
              className="create-novel-fab"
              onClick={() => navigate('/create')}
            >
              +
            </button>
          </>
        )}
      </div>

      {actionSheetVisible && (
        <div className="action-sheet-overlay" onClick={() => setActionSheetVisible(false)}>
          <div className="action-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="action-sheet-header">
              <h3>选择操作</h3>
              <button
                className="close-btn"
                onClick={() => setActionSheetVisible(false)}
              >
                ×
              </button>
            </div>
            <div className="action-sheet-actions">
              <button
                className="action-btn"
                onClick={() => {
                  handleContinueReading(selectedNovel);
                  setActionSheetVisible(false);
                }}
              >
                继续阅读
              </button>
              <button
                className="action-btn"
                onClick={() => handleEditNovel(selectedNovel)}
              >
                编辑小说
              </button>
              <button
                className="action-btn danger"
                onClick={() => handleDeleteNovel(selectedNovel)}
              >
                删除小说
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NovelListPage;