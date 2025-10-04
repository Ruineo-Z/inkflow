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

      // 检查是否有正在生成的章节数据
      const cachedData = localStorage.getItem(`chapter_generating_${novelId}`);
      let isRestoring = false;

      if (cachedData) {
        try {
          const parsed = JSON.parse(cachedData);
          console.log('从localStorage读取的数据:', parsed);
          if (parsed.status === 'generating') {
            // 恢复生成中的章节显示
            const restoredChapter = {
              title: parsed.title || '生成中...',
              content: parsed.content || '',
              isStreaming: true,
              options: []
            };
            console.log('恢复的章节对象:', restoredChapter);
            setCurrentChapter(restoredChapter);
            setGeneratingChapter(true);
            isRestoring = true;
          }
        } catch (e) {
          console.error('解析localStorage数据失败:', e);
          localStorage.removeItem(`chapter_generating_${novelId}`);
        }
      }

      await loadNovel();

      // 只有在不是恢复生成中章节的情况下才加载章节列表
      // 因为loadChapters会覆盖currentChapter
      if (!isRestoring) {
        await loadChapters();
      }

      setLoading(false);
    };

    if (novelId) {
      init();
    }
  }, [novelId, chapterId]);

  // 监听localStorage变化,实时更新生成中的章节内容
  useEffect(() => {
    const handleStorageUpdate = () => {
      const cachedData = localStorage.getItem(`chapter_generating_${novelId}`);
      if (cachedData) {
        try {
          const parsed = JSON.parse(cachedData);
          if (parsed.status === 'generating') {
            console.log('[轮询] 更新内容,标题:', parsed.title, '内容长度:', parsed.content?.length);
            setCurrentChapter(prev => ({
              ...prev,
              title: parsed.title || prev?.title || '生成中...',
              content: parsed.content || prev?.content || '',
              isStreaming: true,
              options: prev?.options || []
            }));
          }
        } catch (e) {
          console.error('监听localStorage更新失败:', e);
        }
      }
    };

    // 使用setInterval轮询localStorage变化(因为同一个标签页内storage事件不会触发)
    const intervalId = setInterval(handleStorageUpdate, 500);

    return () => {
      clearInterval(intervalId);
    };
  }, [novelId]);

  // 选择选项
  const handleOptionSelect = (option) => {
    setSelectedOption(option);
  };

  // 确认选择并生成下一章
  const handleConfirmChoice = async () => {
    if (!selectedOption || !currentChapter) return;

    // 检查章节ID是否有效
    if (!currentChapter.id || currentChapter.id === 'undefined') {
      console.error('Invalid chapter ID:', currentChapter.id);
      showToast('章节信息错误，请刷新页面重试');
      return;
    }

    // 检查选项ID是否有效
    if (!selectedOption.id || selectedOption.id === 'undefined') {
      console.error('Invalid option ID:', selectedOption.id);
      showToast('选项信息错误，请重新选择');
      return;
    }

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

      // 获取resume_token用于断线重连
      const resumeToken = response.headers.get('X-Resume-Token');
      console.log('Resume Token:', resumeToken);

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

        // 测试: 验证离开页面后是否还在接收数据
        console.log('[测试] 收到新数据块,时间:', new Date().toLocaleTimeString());

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

              // 保存标题到localStorage
              localStorage.setItem(`chapter_generating_${novelId}`, JSON.stringify({
                title: streamingChapter.title,
                content: streamingChapter.content,
                resumeToken: resumeToken,
                timestamp: Date.now(),
                status: 'generating'
              }));

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

                  // 保存到localStorage,确保离开页面后也能恢复
                  localStorage.setItem(`chapter_generating_${novelId}`, JSON.stringify({
                    title: streamingChapter.title,
                    content: streamingChapter.content,
                    resumeToken: resumeToken,
                    timestamp: Date.now(),
                    status: 'generating'
                  }));

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

              // 只更新options和isStreaming状态,保持内容不变(避免触发滚动)
              setCurrentChapter(prev => ({
                ...prev,
                options: newChapterData.options,
                isStreaming: false
              }));
              break;
            }
          }
        }
      }

      if (newChapterData) {
        // 章节生成完成,清理localStorage中的临时数据
        localStorage.removeItem(`chapter_generating_${novelId}`);

        // 只更新chapters列表,不调用loadChapters避免重置currentChapter
        // 直接添加新章节到列表末尾
        setChapters(prev => [...prev, {
          id: newChapterData.id,
          chapter_number: prev.length + 1,
          title: newChapterData.title,
          status: 'completed'
        }]);

        // 检查用户是否还在阅读页面
        const currentPath = window.location.pathname;
        const isOnReadingPage = currentPath.includes(`/novels/${novelId}/chapters`) ||
                                currentPath === `/novels/${novelId}`;

        if (isOnReadingPage) {
          // 用户还在阅读页面,更新URL但不触发页面刷新(保持滚动位置)
          window.history.replaceState(null, '', `/novels/${novelId}/chapters/${newChapterData.id}`);
          showToast('新章节生成完成！');
        } else {
          // 用户已经离开,只提示不跳转
          showToast('新章节已生成,可返回查看');
        }

        setSelectedOption(null);
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

  // 第一章生成中的流式显示状态
  if (chapters.length === 0 && (generatingChapter || currentChapter)) {
    return (
      <div className="reading-page">
        <nav className="custom-navbar">
          <button className="nav-back-btn" onClick={() => navigate('/novels')}>
            ←
          </button>
          <h1>{novel?.title || '小说阅读'}</h1>
        </nav>
        <div className="reading-content">
          {/* 显示正在生成的第一章内容 */}
          {currentChapter && (
            <div className="chapter-content">
              <div className="chapter-header">
                <h2 className="chapter-title">
                  {currentChapter.title || '第一章'}
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
                    onClick={handleGenerateFirstChapter}
                  >
                    重新生成第一章
                  </button>
                </div>
              )}
            </div>
          )}

          {/* 只有加载状态，还没有章节内容 */}
          {generatingChapter && !currentChapter && (
            <div className="empty-chapters">
              <div className="loading-spinner">⚡</div>
              <h2>AI正在创作第一章...</h2>
              <p>请稍等，精彩内容即将呈现</p>
            </div>
          )}
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