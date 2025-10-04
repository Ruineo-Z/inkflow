import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ChapterApi, NovelApi } from '../../services/api';
import '../../styles/ReadingPage.css';

const ReadingPage = () => {
  const { id: novelId, chapterId } = useParams();
  const navigate = useNavigate();

  // 页面状态
  const [novel, setNovel] = useState(null);
  const [chapters, setChapters] = useState([]);
  const [currentChapter, setCurrentChapter] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generatingChapter, setGeneratingChapter] = useState(false);
  const [selectedOption, setSelectedOption] = useState(null);
  const [error, setError] = useState(null);

  // 流式连接控制器（用于取消请求）
  const streamAbortController = useRef(null);

  // 显示Toast消息
  const showToast = (message) => {
    const toast = document.createElement('div');
    toast.className = 'custom-toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
      document.body.removeChild(toast);
    }, 3000);
  };

  // 获取API基地址
  const getApiBaseUrl = () => {
    return import.meta.env.VITE_API_BASE_URL
      || (typeof window !== 'undefined' && window.__API_BASE_URL__ && window.__API_BASE_URL__ !== '__API_BASE_URL__' ? window.__API_BASE_URL__ : null)
      || `http://${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:8080/api/v1`;
  };

  // 加载小说信息
  const loadNovel = async () => {
    try {
      const novelData = await NovelApi.getNovelDetail(novelId);
      setNovel(novelData);
    } catch (error) {
      console.error('加载小说失败:', error);
      setError('加载小说信息失败');
    }
  };

  // 加载章节列表
  const loadChapters = async () => {
    try {
      const chaptersData = await ChapterApi.getNovelChapters(novelId);
      setChapters(chaptersData);

      // 如果指定了章节ID，加载对应章节；否则加载最新章节
      if (chapterId) {
        const targetChapter = chaptersData.find(ch => ch.id === parseInt(chapterId));
        if (targetChapter) {
          setCurrentChapter(targetChapter);
        } else {
          showToast('章节不存在');
          navigate(`/novels/${novelId}`);
        }
      } else if (chaptersData.length > 0) {
        // 加载最新章节
        const latestChapter = chaptersData[chaptersData.length - 1];
        setCurrentChapter(latestChapter);
        // 更新URL但不刷新页面
        window.history.replaceState(null, '', `/novels/${novelId}/chapters/${latestChapter.id}`);
      }
    } catch (error) {
      console.error('加载章节失败:', error);
      setError('加载章节列表失败');
    }
  };

  // 取消流式连接
  const abortStream = () => {
    if (streamAbortController.current) {
      console.log('🔌 取消流式连接');
      streamAbortController.current.abort();
      streamAbortController.current = null;
    }
  };

  // 连接到流式接口（使用fetch + ReadableStream）
  const connectToStream = async (chapterId) => {
    // 先取消已有连接
    abortStream();

    const apiBaseUrl = getApiBaseUrl();
    const token = localStorage.getItem('access_token');
    const streamUrl = `${apiBaseUrl}/chapters/${chapterId}/stream`;

    console.log(`📡 连接流式接口: ${streamUrl}`);

    // 创建AbortController
    const controller = new AbortController();
    streamAbortController.current = controller;

    let streamingChapter = {
      id: chapterId,
      title: '',
      content: '',
      options: [],
      isStreaming: true
    };

    try {
      const response = await fetch(streamUrl, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream'
        },
        signal: controller.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // 保留不完整的行

        let currentEvent = null;
        let currentData = '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.substring(6).trim();
          } else if (line.startsWith('data:')) {
            currentData = line.substring(5).trim();

            // 处理不同事件
            if (currentEvent === 'summary') {
              const data = JSON.parse(currentData);
              console.log('📌 [summary]', data.title);
              streamingChapter.title = data.title;

              localStorage.setItem(`chapter_generating_${novelId}`, JSON.stringify({
                chapter_id: chapterId,
                title: streamingChapter.title,
                content: streamingChapter.content,
                status: 'generating',
                timestamp: Date.now()
              }));

              setCurrentChapter({ ...streamingChapter });

            } else if (currentEvent === 'content') {
              const data = JSON.parse(currentData);
              const textChunk = data.text || '';

              if (textChunk) {
                streamingChapter.content += textChunk;

                localStorage.setItem(`chapter_generating_${novelId}`, JSON.stringify({
                  chapter_id: chapterId,
                  title: streamingChapter.title,
                  content: streamingChapter.content,
                  status: 'generating',
                  timestamp: Date.now()
                }));

                setCurrentChapter({ ...streamingChapter });
              }

            } else if (currentEvent === 'complete') {
              const data = JSON.parse(currentData);
              console.log('✅ [complete]', data);

              const finalChapter = {
                id: data.chapter_id,
                title: data.title,
                content: data.content,
                options: data.options ? data.options.map((opt, index) => ({
                  id: opt.id || `temp_${Date.now()}_${index}`,
                  option_text: opt.text || opt.option_text || `选项 ${index + 1}`,
                  impact_description: opt.impact_hint || opt.impact_description || ''
                })) : [],
                isStreaming: false
              };

              setCurrentChapter(finalChapter);
              setGeneratingChapter(false);

              localStorage.removeItem(`chapter_generating_${novelId}`);
              loadChapters();
              showToast('章节生成完成！');

            } else if (currentEvent === 'error') {
              const data = JSON.parse(currentData);
              const errorMsg = data.error || '生成失败';

              console.error('❌ [error]', errorMsg);
              showToast(errorMsg);

              setCurrentChapter(prev => ({
                ...prev,
                isStreaming: false,
                error: errorMsg
              }));
              setGeneratingChapter(false);

              localStorage.removeItem(`chapter_generating_${novelId}`);
            }

            currentEvent = null;
            currentData = '';
          }
        }
      }

    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('🔌 流式连接已取消');
      } else {
        console.error('❌ 流式连接失败:', error);
        showToast(`连接失败: ${error.message}`);
        setGeneratingChapter(false);
      }
    } finally {
      streamAbortController.current = null;
    }
  };

  // 生成章节（新架构：两步调用）
  const generateChapter = async (isFirstChapter = false) => {
    try {
      setGeneratingChapter(true);
      showToast(isFirstChapter ? '正在生成第一章...' : '正在生成下一章...');

      const apiBaseUrl = getApiBaseUrl();
      const token = localStorage.getItem('access_token');

      // Step 1: POST请求开始生成（立即返回chapter_id）
      const response = await fetch(`${apiBaseUrl}/novels/${novelId}/chapters/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({})
      });

      if (!response.ok) {
        throw new Error('生成请求失败');
      }

      const result = await response.json();
      const { chapter_id, status } = result;

      console.log(`🚀 章节生成已启动: chapter_id=${chapter_id}, status=${status}`);

      // 初始化流式章节显示
      setCurrentChapter({
        id: chapter_id,
        title: '生成中...',
        content: '',
        options: [],
        isStreaming: true
      });

      // 保存到localStorage
      localStorage.setItem(`chapter_generating_${novelId}`, JSON.stringify({
        chapter_id: chapter_id,
        title: '生成中...',
        content: '',
        status: 'generating',
        timestamp: Date.now()
      }));

      // Step 2: 连接GET /stream接口获取流式数据
      connectToStream(chapter_id);

    } catch (error) {
      console.error('生成章节失败:', error);
      showToast('生成失败，请重试');
      setGeneratingChapter(false);
    }
  };

  // 选择选项
  const handleOptionSelect = (option) => {
    setSelectedOption(option);
  };

  // 确认选择并生成下一章
  const handleConfirmChoice = async () => {
    if (!selectedOption || !currentChapter) return;

    // 检查章节ID和选项ID
    if (!currentChapter.id || !selectedOption.id) {
      showToast('数据错误，请刷新页面重试');
      return;
    }

    try {
      // 保存用户选择
      await ChapterApi.saveUserChoice(currentChapter.id, selectedOption.id);

      // 生成下一章
      await generateChapter(false);

    } catch (error) {
      console.error('生成章节失败:', error);
      showToast('生成失败，请重试');
      setGeneratingChapter(false);
    }
  };

  // 生成第一章
  const handleGenerateFirstChapter = async () => {
    if (chapters.length > 0) return;
    await generateChapter(true);
  };

  // 章节导航
  const navigateToChapter = (chapter) => {
    navigate(`/novels/${novelId}/chapters/${chapter.id}`);
  };

  // 初始化加载
  useEffect(() => {
    const init = async () => {
      setLoading(true);

      // 检查是否有正在生成的章节（断线重连）
      const cachedData = localStorage.getItem(`chapter_generating_${novelId}`);
      let shouldReconnect = false;
      let reconnectChapterId = null;

      if (cachedData) {
        try {
          const parsed = JSON.parse(cachedData);
          console.log('📦 从localStorage读取:', parsed);

          if (parsed.status === 'generating' && parsed.chapter_id) {
            // 检查时间戳，如果超过10分钟则放弃重连
            const elapsed = Date.now() - parsed.timestamp;
            if (elapsed < 10 * 60 * 1000) {
              shouldReconnect = true;
              reconnectChapterId = parsed.chapter_id;

              // 恢复章节显示
              setCurrentChapter({
                id: reconnectChapterId,
                title: parsed.title || '生成中...',
                content: parsed.content || '',
                options: [],
                isStreaming: true
              });
              setGeneratingChapter(true);

              console.log(`🔄 准备重连到章节 ${reconnectChapterId}`);
            } else {
              console.log('⏰ 生成超时，清理localStorage');
              localStorage.removeItem(`chapter_generating_${novelId}`);
            }
          }
        } catch (e) {
          console.error('解析localStorage失败:', e);
          localStorage.removeItem(`chapter_generating_${novelId}`);
        }
      }

      await loadNovel();

      // 如果需要重连，不加载章节列表（避免覆盖currentChapter）
      if (shouldReconnect && reconnectChapterId) {
        console.log(`🔌 重连到流式接口: chapter ${reconnectChapterId}`);
        connectToStream(reconnectChapterId);
      } else {
        await loadChapters();
      }

      setLoading(false);
    };

    if (novelId) {
      init();
    }

    // 清理函数：组件卸载时取消流式连接
    return () => {
      abortStream();
    };
  }, [novelId, chapterId]);

  // 加载状态
  if (loading) {
    return (
      <div className="reading-page">
        <nav className="custom-navbar">
          <button className="nav-back-btn" onClick={() => navigate('/novels')}>
            ←
          </button>
          <h1>加载中...</h1>
        </nav>
        <div className="reading-content">
          <div className="loading-container">
            <div className="loading-spinner">📖</div>
            <p>正在加载小说内容...</p>
          </div>
        </div>
      </div>
    );
  }

  // 错误状态
  if (error) {
    return (
      <div className="reading-page">
        <nav className="custom-navbar">
          <button className="nav-back-btn" onClick={() => navigate('/novels')}>
            ←
          </button>
          <h1>加载失败</h1>
        </nav>
        <div className="reading-content">
          <div className="error-container">
            <div className="error-icon">😔</div>
            <p>{error}</p>
            <button className="retry-btn" onClick={() => window.location.reload()}>
              重试
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 空章节状态 - 显示生成第一章
  if (chapters.length === 0 && !generatingChapter && !currentChapter) {
    return (
      <div className="reading-page">
        <nav className="custom-navbar">
          <button className="nav-back-btn" onClick={() => navigate('/novels')}>
            ←
          </button>
          <h1>{novel?.title || '小说阅读'}</h1>
        </nav>
        <div className="reading-content">
          <div className="empty-chapters">
            <div className="empty-icon">✨</div>
            <h2>开始你的冒险</h2>
            <p>这部小说还没有章节，点击下方按钮开始生成第一章。</p>
            <button
              className="generate-first-btn"
              onClick={handleGenerateFirstChapter}
              disabled={generatingChapter}
            >
              🚀 开始生成第一章
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 渲染章节内容的公共组件
  const renderChapterContent = () => (
    <div className="chapter-content">
      <div className="chapter-header">
        <h2 className="chapter-title">
          {currentChapter.title || '生成中...'}
        </h2>
        {currentChapter.isStreaming && (
          <p className="streaming-indicator">✨ AI正在创作中...</p>
        )}
        {currentChapter.error && (
          <p className="error-indicator">❌ {currentChapter.error}</p>
        )}
      </div>

      <div className="chapter-text">
        {currentChapter.content && currentChapter.content.trim() ? (
          (() => {
            const contentText = currentChapter.content.trim();
            const paragraphs = contentText
              .split(/\n+/)
              .filter(para => para.trim())
              .map(para => para.trim());

            if (paragraphs.length === 0) {
              return (
                <p className="chapter-paragraph">
                  {contentText}
                  {currentChapter.isStreaming && (
                    <span className="typing-cursor">|</span>
                  )}
                </p>
              );
            }

            return paragraphs.map((paragraph, index) => {
              const isLastParagraph = index === paragraphs.length - 1;
              const shouldShowCursor = currentChapter.isStreaming && isLastParagraph;

              return (
                <p key={index} className="chapter-paragraph">
                  {paragraph}
                  {shouldShowCursor && (
                    <span className="typing-cursor">|</span>
                  )}
                </p>
              );
            });
          })()
        ) : (
          <p className="no-content">
            {currentChapter.isStreaming ? '✨ AI正在构思章节内容...' : '章节内容加载中...'}
          </p>
        )}
      </div>

      {/* 错误状态下的重试按钮 */}
      {currentChapter.error && !currentChapter.isStreaming && (
        <div className="error-actions">
          <button
            className="retry-btn"
            onClick={() => {
              setCurrentChapter({
                ...currentChapter,
                error: null
              });
              if (chapters.length === 0) {
                handleGenerateFirstChapter();
              } else {
                handleConfirmChoice();
              }
            }}
          >
            🔄 重新生成
          </button>
        </div>
      )}

      {/* 选择选项 - 仅在非流式状态且有选项时显示 */}
      {!currentChapter.isStreaming && !currentChapter.error && currentChapter.options && currentChapter.options.length > 0 && (
        <div className="chapter-options">
          <h3 className="options-title">选择你的行动：</h3>
          <div className="options-list">
            {currentChapter.options.map((option, index) => (
              <div
                key={option.id}
                className={`option-card ${selectedOption?.id === option.id ? 'selected' : ''}`}
                onClick={() => handleOptionSelect(option)}
              >
                <div className="option-number">{index + 1}</div>
                <div className="option-content">
                  <p className="option-text">{option.option_text}</p>
                </div>
              </div>
            ))}
          </div>

          {selectedOption && (
            <div className="choice-confirm">
              <button
                className="confirm-choice-btn"
                onClick={handleConfirmChoice}
                disabled={generatingChapter}
              >
                {generatingChapter ? (
                  <>
                    <span className="loading-spinner">⚡</span>
                    正在生成下一章...
                  </>
                ) : (
                  '✨ 确认选择并继续'
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );

  // 正常阅读界面
  return (
    <div className="reading-page">
      <nav className="custom-navbar">
        <button className="nav-back-btn" onClick={() => navigate('/novels')}>
          ←
        </button>
        <h1>{novel?.title || '小说阅读'}</h1>
        <div className="chapter-nav">
          <span className="chapter-counter">
            {currentChapter && chapters.length > 0 &&
              `${chapters.findIndex(ch => ch.id === currentChapter.id) + 1}/${chapters.length}`
            }
          </span>
        </div>
      </nav>

      <div className="reading-content">
        {/* 章节内容 */}
        {currentChapter && renderChapterContent()}

        {/* 生成中但还没有内容 */}
        {generatingChapter && !currentChapter && (
          <div className="empty-chapters">
            <div className="loading-spinner">⚡</div>
            <h2>AI正在创作中...</h2>
            <p>请稍等，精彩内容即将呈现</p>
          </div>
        )}

        {/* 章节导航 */}
        {chapters.length > 1 && (
          <div className="chapter-navigation">
            <h3>章节导航</h3>
            <div className="chapters-list">
              {chapters.map((chapter, index) => (
                <div
                  key={chapter.id}
                  className={`chapter-item ${currentChapter?.id === chapter.id ? 'current' : ''}`}
                  onClick={() => navigateToChapter(chapter)}
                >
                  <div className="chapter-number">第{index + 1}章</div>
                  <div className="chapter-info">
                    <h4 className="chapter-item-title">{chapter.title}</h4>
                    {chapter.summary && (
                      <p className="chapter-item-summary">{chapter.summary}</p>
                    )}
                  </div>
                  {chapter.selected_option_id && (
                    <div className="chapter-status">✓</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReadingPage;
