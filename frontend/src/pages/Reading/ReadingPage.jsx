import { useState, useEffect, useCallback } from 'react';
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
  const [isRecoveringGeneration, setIsRecoveringGeneration] = useState(false);
  const [sseController, setSseController] = useState(null);

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

  // 生成状态管理
  const GENERATION_STATE_KEY = `generation_state_${novelId}`;

  // 保存生成状态到localStorage
  const saveGenerationState = useCallback((state) => {
    try {
      localStorage.setItem(GENERATION_STATE_KEY, JSON.stringify({
        ...state,
        novelId,
        timestamp: Date.now()
      }));
    } catch (error) {
      console.error('保存生成状态失败:', error);
    }
  }, [novelId]);

  // 获取生成状态
  const getGenerationState = useCallback(() => {
    try {
      const saved = localStorage.getItem(GENERATION_STATE_KEY);
      if (saved) {
        const state = JSON.parse(saved);
        // 检查状态是否过期（30分钟）
        if (Date.now() - state.timestamp < 30 * 60 * 1000) {
          return state;
        }
      }
    } catch (error) {
      console.error('获取生成状态失败:', error);
    }
    return null;
  }, []);

  // 清除生成状态
  const clearGenerationState = useCallback(() => {
    try {
      localStorage.removeItem(GENERATION_STATE_KEY);
    } catch (error) {
      console.error('清除生成状态失败:', error);
    }
  }, []);

  // 检查并处理未完成的生成状态
  const checkAndHandleIncompleteGeneration = useCallback(async () => {
    const savedState = getGenerationState();
    if (savedState && savedState.isGenerating) {
      console.log('检测到未完成的生成任务');
      
      // 刷新页面后，SSE连接已断开，后端状态也已丢失
      // 不尝试恢复连接，而是提供重新生成的选项
      clearGenerationState();
      
      // 设置状态以显示重新生成提示
      setError({
        type: 'incomplete_generation',
        message: '检测到未完成的生成任务',
        savedState: savedState
      });
      
      showToast('检测到未完成的生成任务，请选择重新生成或取消');
    }
  }, [getGenerationState, clearGenerationState]);

  // 获取API基地址
  const getApiBaseUrl = () => {
    return import.meta.env.VITE_API_BASE_URL
      || (typeof window !== 'undefined' && window.__API_BASE_URL__ && window.__API_BASE_URL__ !== '__API_BASE_URL__' ? window.__API_BASE_URL__ : null)
      || `http://${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:8000/api/v1`;
  };

  // 加载小说信息
  const loadNovel = useCallback(async () => {
    try {
      const novelData = await NovelApi.getNovelDetail(novelId);
      setNovel(novelData);
    } catch (error) {
      console.error('加载小说失败:', error);
      setError('加载小说信息失败');
    }
  }, [novelId]);

  // 加载章节列表
  const loadChapters = useCallback(async () => {
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
  }, [novelId, chapterId, navigate]);

  // 初始化加载
  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await Promise.all([loadNovel(), loadChapters()]);
      // 检查是否有未完成的生成任务
      await checkAndHandleIncompleteGeneration();
      setLoading(false);
    };

    if (novelId) {
      init();
    }
  }, [novelId, chapterId, loadNovel, loadChapters, checkAndHandleIncompleteGeneration]);

  // 页面离开时保存生成状态
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (generatingChapter) {
        saveGenerationState({
          isGenerating: true,
          currentChapter,
          selectedOption
        });
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden && generatingChapter) {
        saveGenerationState({
          isGenerating: true,
          currentChapter,
          selectedOption
        });
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      
      // 清理SSE连接
      if (sseController) {
        sseController.abort();
      }
    };
  }, [generatingChapter, currentChapter, selectedOption, sseController, saveGenerationState]);

  // 选择选项
  const handleOptionSelect = (option) => {
    console.log('🎯 用户选择选项:', option);
    setSelectedOption(option);
  };

  // 确认选择并生成下一章
  const handleConfirmChoice = async () => {
    console.log('📝 handleConfirmChoice 开始执行');
    console.log('selectedOption:', selectedOption);
    console.log('currentChapter:', currentChapter);
    
    if (!selectedOption || !currentChapter) {
      console.error('❌ 缺少必要参数:', { selectedOption, currentChapter });
      showToast('请先选择一个选项再确认');
      return;
    }

    // 检查章节ID是否有效
    if (!currentChapter.id || currentChapter.id === 'undefined') {
      console.error('❌ Invalid chapter ID:', currentChapter.id);
      showToast('章节信息错误，请刷新页面重试');
      return;
    }

    // 检查选项ID是否有效
    if (!selectedOption.id || selectedOption.id === 'undefined') {
      console.error('❌ Invalid option ID:', selectedOption.id);
      showToast('选项信息错误，请重新选择');
      return;
    }

    try {
      console.log('💾 开始保存用户选择...');
      // 保存用户选择
      await ChapterApi.saveUserChoice(currentChapter.id, selectedOption.id);
      console.log('✅ 用户选择保存成功');

      // 开始生成下一章
      console.log('🚀 开始生成下一章...');
      setGeneratingChapter(true);
      showToast('正在生成下一章节...');

      // 保存生成状态
      saveGenerationState({
        isGenerating: true,
        currentChapter: currentChapter,
        selectedOption: selectedOption
      });

      // 调用章节生成API（流式）
      await generateNextChapter();

    } catch (error) {
      console.error('❌ 生成章节失败:', error);
      console.error('错误详情:', {
        message: error.message,
        stack: error.stack,
        name: error.name
      });
      
      // 显示更详细的错误信息
      let errorMessage = '生成失败，请重试';
      if (error.message.includes('fetch')) {
        errorMessage = '网络连接失败，请检查后端服务是否运行';
      } else if (error.message.includes('401')) {
        errorMessage = '认证失败，请重新登录';
      } else if (error.message.includes('500')) {
        errorMessage = '服务器内部错误，请稍后重试';
      }
      
      showToast(errorMessage);
      setGeneratingChapter(false);
      clearGenerationState();
    }
  };

  // 基于已选择重新生成下一章（不调用choice接口）
  const handleRegenerateChapter = async () => {
    if (!currentChapter) return;

    try {
      console.log('🔄 开始重新生成下一章');
      console.log('当前章节:', currentChapter);
      console.log('API基地址:', getApiBaseUrl());
      console.log('认证Token存在:', !!localStorage.getItem('access_token'));
      
      // 直接开始生成，不调用choice接口（因为用户已经选择过了）
      setGeneratingChapter(true);
      showToast('正在重新生成下一章节...');

      // 保存生成状态
      saveGenerationState({
        isGenerating: true,
        currentChapter: currentChapter,
        selectedOption: null // 重新生成时不需要selectedOption
      });

      // 直接调用章节生成API（流式）
      await generateNextChapter();

    } catch (error) {
      console.error('❌ 重新生成章节失败:', error);
      let errorMessage = '重新生成失败，请重试';
      
      if (error.message.includes('401')) {
        errorMessage = '认证失败，请重新登录';
      } else if (error.message.includes('403')) {
        errorMessage = '权限不足，请检查账户状态';
      } else if (error.message.includes('500')) {
        errorMessage = '服务器错误，请稍后重试';
      } else if (error.message.includes('Network')) {
        errorMessage = '网络连接失败，请检查网络';
      }
      
      showToast(errorMessage);
      setGeneratingChapter(false);
      clearGenerationState();
    }
  };



  // 生成下一章节（流式处理）- 使用fetch处理SSE格式响应
  const generateNextChapter = async () => {
    console.log('🎯 generateNextChapter 开始执行');
    
    // 创建新的AbortController用于取消请求
    const controller = new AbortController();
    setSseController(controller);

    try {
      const apiBaseUrl = getApiBaseUrl();
      const endpoint = `${apiBaseUrl}/novels/${novelId}/chapters/generate`;
      const token = localStorage.getItem('access_token');
      
      console.log('🌐 API调用信息:', {
        endpoint,
        novelId,
        hasToken: !!token,
        tokenPrefix: token ? token.substring(0, 10) + '...' : 'null'
      });

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({}),
        signal: controller.signal
      });

      console.log('📡 API响应状态:', {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        headers: Object.fromEntries(response.headers.entries())
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ API响应错误:', {
          status: response.status,
          statusText: response.statusText,
          errorText
        });
        throw new Error(`生成请求失败: ${response.status} ${response.statusText} - ${errorText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let newChapterData = null;
      let streamingChapter = {
        title: '',
        content: '',
        options: []
      };

      // 创建流式章节显示
      setCurrentChapter({
        ...streamingChapter,
        isStreaming: true
      });

      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;

        // 处理SSE格式的数据：event: xxx\ndata: {json}\n\n
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // 保留最后一个可能不完整的行

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i].trim();
          
          if (line.startsWith('event:')) {
            const eventType = line.substring(6).trim();
            const dataLine = lines[i + 1];
            
            if (dataLine && dataLine.startsWith('data:')) {
              try {
                const eventData = JSON.parse(dataLine.substring(5).trim());
                
                if (eventType === 'summary') {
                  console.log('📝 收到summary事件:', eventData);
                  streamingChapter.title = eventData.title;
                  setCurrentChapter({
                    ...streamingChapter,
                    isStreaming: true
                  });
                } else if (eventType === 'content') {
                  console.log('📄 收到content事件:', eventData);
                  if (eventData.text) {
                    streamingChapter.content += eventData.text;
                    setCurrentChapter({
                      ...streamingChapter,
                      isStreaming: true
                    });
                  }
                } else if (eventType === 'complete') {
                  console.log('✅ 收到complete事件:', eventData);
                  
                  newChapterData = {
                    id: eventData.chapter_id || Date.now(),
                    title: eventData.title || streamingChapter.title || '未知章节',
                    content: eventData.content || streamingChapter.content || '',
                    options: eventData.options ? eventData.options.map((opt, index) => ({
                      id: opt.id || `temp_${Date.now()}_${index}`,
                      option_text: opt.text || opt.option_text || `选项 ${index + 1}`,
                      impact_description: opt.impact_hint || opt.impact_description || ''
                    })) : []
                  };

                  // 设置最终完整的章节
                  setCurrentChapter({
                    ...newChapterData,
                    isStreaming: false
                  });
                  break;
                } else if (eventType === 'error') {
                  console.error('❌ 收到error事件:', eventData);
                  showToast(`生成失败: ${eventData.error || '未知错误'}`);
                  setCurrentChapter({
                    ...streamingChapter,
                    isStreaming: false,
                    error: eventData.error || '生成过程中发生错误'
                  });
                  setGeneratingChapter(false);
                  return;
                }
              } catch (parseError) {
                console.error('解析SSE事件数据失败:', parseError, 'data:', dataLine);
              }
              i++; // 跳过data行
            }
          }
        }
      }

      if (newChapterData) {
        // 清除生成状态
        clearGenerationState();
        
        // 重新加载章节列表
        await loadChapters();

        // 导航到新章节
        navigate(`/novels/${novelId}/chapters/${newChapterData.id}`);
        setSelectedOption(null);
        showToast('新章节生成完成！');
      }

    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('生成被中断');
        return;
      }
      console.error('流式生成失败:', error);
      clearGenerationState();
      throw error;
    } finally {
      setGeneratingChapter(false);
      setSseController(null);
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
      
      // 保存生成状态
      saveGenerationState({
        isGenerating: true,
        currentChapter: null,
        selectedOption: null
      });
      
      await generateNextChapter();
    } catch (error) {
      console.error('❌ generateNextChapter 执行失败:', error);
      console.error('错误详情:', {
        message: error.message,
        stack: error.stack,
        name: error.name,
        cause: error.cause
      });
      
      // 根据错误类型显示不同的提示信息
      let errorMessage = '生成失败，请重试';
      if (error.name === 'AbortError') {
        errorMessage = '生成已取消';
        console.log('🛑 用户取消了生成过程');
      } else if (error.message.includes('Failed to fetch')) {
        errorMessage = '网络连接失败，请检查后端服务状态';
      } else if (error.message.includes('401')) {
        errorMessage = '认证失败，请重新登录';
      } else if (error.message.includes('500')) {
        errorMessage = '服务器内部错误，请稍后重试';
      } else if (error.message.includes('400')) {
        errorMessage = '请求参数错误，请检查选项是否有效';
      }
      
      showToast(errorMessage);
      setGeneratingChapter(false);
      clearGenerationState();
      
      // 设置错误状态以显示重试按钮
      setCurrentChapter(prev => ({
        ...prev,
        error: errorMessage,
        isStreaming: false
      }));
    }
  };

  // 加载状态
  if (loading || isRecoveringGeneration) {
    return (
      <div className="reading-page">
        <nav className="custom-navbar">
          <button className="nav-back-btn" onClick={() => navigate('/novels')}>
            ←
          </button>
          <h1>{isRecoveringGeneration ? '恢复生成中...' : '加载中...'}</h1>
        </nav>
        <div className="reading-content">
          <div className="loading-container">
            <div className="loading-spinner">{isRecoveringGeneration ? '⚡' : '📖'}</div>
            <p>{isRecoveringGeneration ? '正在恢复生成进度，请稍候...' : '正在加载小说内容...'}</p>
            {isRecoveringGeneration && (
              <button 
                className="retry-btn"
                onClick={() => {
                  clearGenerationState();
                  setIsRecoveringGeneration(false);
                  showToast('已取消恢复，请手动重新生成');
                }}
              >
                取消恢复
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // 错误状态
  if (error) {
    // 特殊处理未完成生成任务的情况
    if (error.type === 'incomplete_generation') {
      return (
        <div className="reading-page">
          <nav className="custom-navbar">
            <button className="nav-back-btn" onClick={() => navigate('/novels')}>
              ←
            </button>
            <h1>{novel?.title || '小说阅读'}</h1>
          </nav>
          <div className="reading-content">
            <div className="incomplete-generation-container">
              <div className="warning-icon">⚠️</div>
              <h2>检测到未完成的生成任务</h2>
              <p>页面刷新导致生成过程中断，您可以选择：</p>
              <div className="action-buttons">
                <button 
                  className="regenerate-btn"
                  onClick={() => {
                    setError(null);
                    // 如果有保存的选项，恢复选项状态
                    if (error.savedState?.selectedOption) {
                      setSelectedOption(error.savedState.selectedOption);
                    }
                    // 重新开始生成
                    if (chapters.length === 0) {
                      handleGenerateFirstChapter();
                    } else {
                      handleConfirmChoice();
                    }
                  }}
                >
                  🔄 重新生成
                </button>
                <button 
                  className="cancel-btn"
                  onClick={() => {
                    setError(null);
                    showToast('已取消生成任务');
                  }}
                >
                  ❌ 取消
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    // 普通错误状态
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
            <p>{typeof error === 'string' ? error : error.message || '未知错误'}</p>
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
                {currentChapter.selected_option_id ? (
                  <h3 className="options-title">你的选择：</h3>
                ) : (
                  <div className="options-header">
                    <h3 className="options-title">选择你的行动：</h3>
                    {!selectedOption && (
                      <p className="options-instruction">👆 点击下方选项进行选择</p>
                    )}
                  </div>
                )}
                <div className="options-list">
                  {currentChapter.options.map((option, index) => {
                    const isSelected = currentChapter.selected_option_id === option.id;
                    const hasUserChoice = currentChapter.selected_option_id !== null && currentChapter.selected_option_id !== undefined;
                    
                    return (
                      <div
                        key={option.id}
                        className={`option-card ${
                          isSelected ? 'user-selected' : 
                          (!hasUserChoice && selectedOption?.id === option.id) ? 'selected' : ''
                        } ${hasUserChoice ? 'disabled' : ''}`}
                        onClick={hasUserChoice ? undefined : () => handleOptionSelect(option)}
                      >
                        <div className="option-number">{index + 1}</div>
                        <div className="option-content">
                          <p className="option-text">{option.option_text}</p>
                          {isSelected && (
                            <div className="selected-indicator">
                              <span className="selected-icon">✓</span>
                              <span className="selected-text">已选择</span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {!currentChapter.selected_option_id && (
                  <div className="choice-confirm">
                    {!selectedOption && (
                      <p className="selection-hint">💡 请先选择一个选项</p>
                    )}
                    <button
                      className={`confirm-choice-btn ${!selectedOption ? 'disabled' : ''}`}
                      onClick={handleConfirmChoice}
                      disabled={generatingChapter || !selectedOption}
                    >
                      {generatingChapter ? (
                        <>
                          <span className="loading-spinner">⚡</span>
                          正在生成下一章...
                        </>
                      ) : !selectedOption ? (
                        '请先选择选项'
                      ) : (
                        '✨ 确认选择并继续'
                      )}
                    </button>
                  </div>
                )}

                {currentChapter.selected_option_id && (
                  <div className="choice-status">
                    <p className="status-text">你已经做出了选择，故事将继续发展...</p>
                    {/* 检查是否是最后一章且没有下一章，提供重新生成选项 */}
                    {(() => {
                      const currentIndex = chapters.findIndex(ch => ch.id === currentChapter.id);
                      const isLastChapter = currentIndex === chapters.length - 1;
                      const hasNextChapter = currentIndex < chapters.length - 1;
                      
                      // 如果是最后一章且用户已选择但没有下一章，说明生成中断了
                      if (isLastChapter && !hasNextChapter && currentChapter.selected_option_id) {
                        return (
                          <div className="regenerate-section">
                            <p className="regenerate-hint">⚠️ 检测到生成过程可能中断，下一章尚未生成</p>
                            <button
                              className="regenerate-choice-btn"
                              onClick={() => {
                                console.log('🔄 重新生成按钮被点击');
                                console.log('当前章节:', currentChapter);
                                console.log('章节列表:', chapters);
                                
                                // 直接重新生成下一章，不需要重新选择
                                handleRegenerateChapter();
                              }}
                              disabled={generatingChapter}
                            >
                              {generatingChapter ? (
                                <>
                                  <span className="loading-spinner">⚡</span>
                                  正在重新生成...
                                </>
                              ) : (
                                '🔄 基于已选择重新生成下一章'
                              )}
                            </button>
                          </div>
                        );
                      }
                      return null;
                    })()} 
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