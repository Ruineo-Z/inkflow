import { useState, useEffect } from 'react';
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

  // 初始化加载
  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await Promise.all([loadNovel(), loadChapters()]);
      setLoading(false);
    };

    if (novelId) {
      init();
    }
  }, [novelId, chapterId]);

  // 选择选项
  const handleOptionSelect = (option) => {
    setSelectedOption(option);
  };

  // 确认选择并生成下一章
  const handleConfirmChoice = async () => {
    if (!selectedOption || !currentChapter) return;

    try {
      // 保存用户选择
      await ChapterApi.saveUserChoice(currentChapter.id, selectedOption.id);

      // 开始生成下一章
      setGeneratingChapter(true);
      showToast('正在生成下一章节...');

      // 调用章节生成API（流式）
      await generateNextChapter();

    } catch (error) {
      console.error('生成章节失败:', error);
      showToast('生成失败，请重试');
      setGeneratingChapter(false);
    }
  };

  // 生成下一章节（流式处理）
  const generateNextChapter = async () => {
    try {
      // 获取API基地址
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL
        || (typeof window !== 'undefined' && window.__API_BASE_URL__ && window.__API_BASE_URL__ !== '__API_BASE_URL__' ? window.__API_BASE_URL__ : null)
        || `http://${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:8000/api/v1`;

      const response = await fetch(`${apiBaseUrl}/novels/${novelId}/chapters/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({})
      });

      if (!response.ok) {
        throw new Error('生成请求失败');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let newChapterData = null;
      let streamingChapter = {
        title: '',
        content: '',
        options: []
      };

      // 累积的原始JSON字符串，用于智能解析
      let accumulatedJson = '';

      // 创建流式章节显示
      setCurrentChapter({
        ...streamingChapter,
        isStreaming: true
      });

      // 尝试从累积的JSON中提取content字段
      const tryExtractContent = (jsonStr) => {
        try {
          // 尝试多种方式解析部分JSON
          let content = '';

          // 方法1: 使用正则表达式寻找content字段
          // 支持处理转义字符和多行内容
          const contentMatch = jsonStr.match(/"content"\s*:\s*"((?:[^"\\]|\\.)*)"/s);
          if (contentMatch) {
            content = contentMatch[1]
              .replace(/\\n/g, '\n')
              .replace(/\\"/g, '"')
              .replace(/\\t/g, '\t')
              .replace(/\\\\/g, '\\');
            return content;
          }

          // 方法2: 尝试直接JSON解析完整对象
          try {
            const parsed = JSON.parse(jsonStr);
            if (parsed.content) {
              return parsed.content;
            }
          } catch (e) {
            // 继续尝试其他方法
          }

          // 方法3: 处理不完整的JSON，尝试补全并解析
          if (jsonStr.includes('"content"')) {
            // 寻找content字段到字符串结束的部分
            const contentStart = jsonStr.indexOf('"content"');
            let valueStart = jsonStr.indexOf(':', contentStart);
            if (valueStart !== -1) {
              valueStart = jsonStr.indexOf('"', valueStart) + 1;
              if (valueStart > 0) {
                // 找到可能的content值
                let currentPos = valueStart;
                let content = '';
                let escapeNext = false;

                while (currentPos < jsonStr.length) {
                  const char = jsonStr[currentPos];

                  if (escapeNext) {
                    // 处理转义字符
                    if (char === 'n') content += '\n';
                    else if (char === 't') content += '\t';
                    else if (char === '"') content += '"';
                    else if (char === '\\') content += '\\';
                    else content += char;
                    escapeNext = false;
                  } else if (char === '\\') {
                    escapeNext = true;
                  } else if (char === '"') {
                    // 找到字符串结束
                    break;
                  } else {
                    content += char;
                  }

                  currentPos++;
                }

                return content;
              }
            }
          }

          return '';
        } catch (e) {
          console.debug('JSON解析失败:', e);
          return '';
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];

          if (line.startsWith('event: error')) {
            // 处理错误事件
            const dataLine = lines[i + 1];
            if (dataLine && dataLine.startsWith('data: ')) {
              const errorData = JSON.parse(dataLine.substring(6));
              console.error('流式生成错误:', errorData);
              showToast(`生成失败: ${errorData.error || '未知错误'}`);
              setCurrentChapter({
                ...streamingChapter,
                isStreaming: false,
                error: errorData.error || '生成过程中发生错误'
              });
              setGeneratingChapter(false);
              return;
            }
          } else if (line.startsWith('event: summary')) {
            const dataLine = lines[i + 1];
            if (dataLine && dataLine.startsWith('data: ')) {
              const data = JSON.parse(dataLine.substring(6));
              streamingChapter.title = data.title;
              setCurrentChapter({
                ...streamingChapter,
                isStreaming: true
              });
            }
          } else if (line.startsWith('event: content')) {
            const dataLine = lines[i + 1];
            if (dataLine && dataLine.startsWith('data: ')) {
              const data = JSON.parse(dataLine.substring(6));
              // 后端发送的是原始JSON片段
              let textChunk = data.text || '';

              if (textChunk.trim()) {
                // 累积原始JSON
                accumulatedJson += textChunk;

                // 尝试从累积的JSON中提取content
                const extractedContent = tryExtractContent(accumulatedJson);

                if (extractedContent && extractedContent !== streamingChapter.content) {
                  streamingChapter.content = extractedContent;

                  // 实时更新章节显示
                  setCurrentChapter({
                    ...streamingChapter,
                    isStreaming: true
                  });
                }
              }
            }
          } else if (line.startsWith('event: complete')) {
            const dataLine = lines[i + 1];
            if (dataLine && dataLine.startsWith('data: ')) {
              try {
                const data = JSON.parse(dataLine.substring(6));
                console.log('Complete event data:', data);

                // 使用complete事件的完整数据
                newChapterData = {
                  id: data.chapter_id || Date.now(),
                  title: data.title || streamingChapter.title || '未知章节',
                  content: data.content || streamingChapter.content || '',
                  options: data.options ? data.options.map((opt, index) => ({
                    id: opt.id || `temp_${Date.now()}_${index}`,
                    option_text: opt.text || opt.option_text || `选项 ${index + 1}`,
                    impact_description: opt.impact_hint || opt.impact_description || ''
                  })) : []
                };

                console.log('Final chapter data:', newChapterData);

              } catch (parseError) {
                console.error('Failed to parse complete event data:', parseError);
                // 解析失败时尝试使用流式数据
                newChapterData = {
                  id: Date.now(),
                  title: streamingChapter.title || '未知章节',
                  content: streamingChapter.content || '',
                  options: []
                };
              }

              // 设置最终完整的章节
              setCurrentChapter({
                ...newChapterData,
                isStreaming: false
              });
              break;
            }
          }
        }
      }

      if (newChapterData) {
        // 重新加载章节列表
        await loadChapters();

        // 导航到新章节
        navigate(`/novels/${novelId}/chapters/${newChapterData.id}`);
        setSelectedOption(null);
        showToast('新章节生成完成！');
      }

    } catch (error) {
      console.error('流式生成失败:', error);
      throw error;
    } finally {
      setGeneratingChapter(false);
    }
  };

  // 章节导航
  const navigateToChapter = (chapter) => {
    navigate(`/novels/${novelId}/chapters/${chapter.id}`);
  };

  // 如果没有章节，显示生成第一章的界面
  const handleGenerateFirstChapter = async () => {
    if (chapters.length > 0) return;

    try {
      setGeneratingChapter(true);
      showToast('正在生成第一章...');
      await generateNextChapter();
    } catch (error) {
      console.error('生成第一章失败:', error);
      showToast('生成失败，请重试');
      setGeneratingChapter(false);
    }
  };

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
  if (chapters.length === 0) {
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
              {generatingChapter ? (
                <>
                  <span className="loading-spinner">⚡</span>
                  AI正在创作第一章...
                </>
              ) : (
                '🚀 开始生成第一章'
              )}
            </button>
          </div>
        </div>
      </div>
    );
  }

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
        {currentChapter && (
          <div className="chapter-content">
            <div className="chapter-header">
              <h2 className="chapter-title">{currentChapter.title}</h2>
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
                  // 简化段落处理逻辑，确保实时渲染效果
                  let contentText = currentChapter.content.trim();

                  // 将内容按段落分割 - 支持单换行符和双换行符
                  const paragraphs = contentText
                    .split(/\n+/) // 按换行符分割
                    .filter(para => para.trim()) // 过滤空段落
                    .map(para => para.trim()); // 清理首尾空白

                  // 如果没有分割成功，直接显示整个内容
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

                  // 渲染每个段落
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