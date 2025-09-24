import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { NovelApi, ChapterApi } from '../../services/api';

const ReadingPage = () => {
  const navigate = useNavigate();
  const { id: novelId } = useParams();
  const [novel, setNovel] = useState(null);
  const [currentChapter, setCurrentChapter] = useState(null);
  const [selectedOption, setSelectedOption] = useState(null);
  const [generatingChapter, setGeneratingChapter] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const sseControllerRef = useRef(null);

  // 显示Toast消息
  const showToast = (message) => {
    alert(message); // 简化版Toast
  };

  // API基地址获取函数
  const getApiBaseUrl = () => {
    return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
  };

  // 生成下一章节的函数（setInterval轮询机制）
  const generateNextChapter = async () => {
    if (!novelId) {
      console.error('❌ 缺少novelId');
      return;
    }

    // 创建新的AbortController用于取消请求
    const controller = new AbortController();

    try {
      const apiBaseUrl = getApiBaseUrl();
      const token = localStorage.getItem('access_token');

      // 第一步：创建生成任务
      console.log('🚀 创建章节生成任务');
      const createTaskEndpoint = `${apiBaseUrl}/novels/${novelId}/chapters/generate`;
      const createTaskResponse = await fetch(createTaskEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({}),
        signal: controller.signal
      });

      if (!createTaskResponse.ok) {
        const errorText = await createTaskResponse.text();
        console.error('❌ 创建任务失败:', {
          status: createTaskResponse.status,
          statusText: createTaskResponse.statusText,
          errorText
        });
        throw new Error(`创建生成任务失败: ${createTaskResponse.status} ${createTaskResponse.statusText}`);
      }

      const taskData = await createTaskResponse.json();
      const taskId = taskData.task_id;
      console.log('✅ 生成任务创建成功，任务ID:', taskId);

      // 第二步：轮询获取增量内容
      let streamingChapter = {
        title: '',
        content: '',
        options: []
      };

      let chunks_received = 0;
      let is_complete = false;
      let polls = 0;
      const max_polls = 60; // 最多轮询60次（2分钟）

      // 创建流式章节显示
      setCurrentChapter({
        ...streamingChapter,
        isStreaming: true
      });

      console.log('🔄 开始轮询增量内容... 使用setInterval机制');

      // 返回Promise，在轮询完成时resolve
      await new Promise((resolve, reject) => {
        // 使用setInterval确保轮询持续进行
        const intervalId = setInterval(async () => {
          if (controller.signal.aborted) {
            console.log('🏁 轮询被中断');
            clearInterval(intervalId);
            resolve();
            return;
          }

          if (polls >= max_polls) {
            console.log('🏁 轮询超时');
            clearInterval(intervalId);
            resolve();
            return;
          }

          if (is_complete) {
            console.log('🏁 轮询完成!');
            clearInterval(intervalId);
            setGeneratingChapter(false);
            resolve();
            return;
          }

          polls++;
          console.log(`🔄 [轮询 ${polls.toString().padStart(2, '0')}] 开始第 ${polls} 次轮询`);

          try {
            const contentEndpoint = `${apiBaseUrl}/novels/${novelId}/chapters/generate/${taskId}/content`;
            const contentResponse = await fetch(`${contentEndpoint}?from_chunk=${chunks_received}`, {
              method: 'GET',
              headers: {
                'Authorization': `Bearer ${token}`
              },
              signal: controller.signal
            });

            console.log(`📡 [轮询 ${polls.toString().padStart(2, '0')}] API调用完成, 状态: ${contentResponse.status}`);

            if (!contentResponse.ok) {
              console.error('❌ 获取内容失败:', contentResponse.status, contentResponse.statusText);
              if (contentResponse.status === 401) {
                console.error('❌ Token过期，停止轮询');
                clearInterval(intervalId);
                reject(new Error('认证失败，请重新登录'));
                return;
              }
              // 其他错误继续轮询
              return;
            }

            const contentData = await contentResponse.json();
            const newChunks = contentData.chunks || [];
            is_complete = contentData.is_complete || false;
            const progress = contentData.progress || 0;

            console.log(`📊 [轮询 ${polls.toString().padStart(2, '0')}] 进度: ${progress}%, 新chunks: ${newChunks.length}, 完成: ${is_complete}`);

            // 处理新的chunks
            if (newChunks.length > 0) {
              console.log(`📝 [轮询 ${polls.toString().padStart(2, '0')}] 处理 ${newChunks.length} 个新chunks`);
              for (const chunk of newChunks) {
                if (chunk.type === 'title') {
                  streamingChapter.title = chunk.text;
                  console.log('📝 更新标题:', chunk.text);
                } else if (chunk.type === 'content') {
                  streamingChapter.content += chunk.text;
                  console.log('📄 添加内容片段:', chunk.text.substring(0, 50) + '...');
                } else if (chunk.type === 'separator') {
                  streamingChapter.content += '\n\n';
                } else if (chunk.type === 'option') {
                  // 解析选项JSON
                  try {
                    const optionData = JSON.parse(chunk.text);
                    streamingChapter.options.push({
                      id: optionData.id || `temp_${Date.now()}_${streamingChapter.options.length}`,
                      option_text: optionData.text || optionData.option_text || `选项 ${streamingChapter.options.length + 1}`,
                      impact_description: optionData.impact_hint || optionData.impact_description || ''
                    });
                    console.log('🎯 添加选项:', optionData);
                  } catch (parseError) {
                    console.error('❌ 解析选项失败:', parseError, chunk.text);
                  }
                }
              }

              chunks_received = contentData.next_chunk_index || chunks_received;

              // 更新UI显示
              setCurrentChapter({
                ...streamingChapter,
                isStreaming: !is_complete
              });
            } else {
              console.log(`⏳ [轮询 ${polls.toString().padStart(2, '0')}] 无新内容`);
            }

          } catch (fetchError) {
            if (fetchError.name === 'AbortError') {
              console.log('轮询被中断');
              clearInterval(intervalId);
              resolve();
              return;
            }
            console.error('❌ 轮询请求失败:', fetchError);
            console.error('❌ 错误详细信息:', {
              name: fetchError.name,
              message: fetchError.message
            });

            // 认证错误停止轮询
            if (fetchError.message.includes('认证失败')) {
              clearInterval(intervalId);
              reject(fetchError);
              return;
            }
            // 其他错误继续轮询
          }
        }, 2000); // 每2秒轮询一次

        // 保存interval ID到ref中，以便清理
        sseControllerRef.current = { controller, intervalId };
      });

    } catch (error) {
      console.error('❌ generateNextChapter 发生错误:', error);
      setGeneratingChapter(false);
      throw error;
    }
  };

  // 选择选项并生成下一章
  const handleOptionSelect = async (selectedOption) => {
    console.log('🎯 用户选择选项:', selectedOption);

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

      // 调用章节生成API（流式）
      await generateNextChapter();

    } catch (error) {
      console.error('❌ 生成章节失败:', error);
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
    }
  };

  // 开始生成第一章
  const handleGenerateFirstChapter = async () => {
    try {
      setGeneratingChapter(true);
      showToast('正在生成第一章...');
      await generateNextChapter();
    } catch (error) {
      console.error('❌ 生成第一章失败:', error);
      let errorMessage = '生成失败，请重试';
      if (error.message.includes('401')) {
        errorMessage = '认证失败，请重新登录';
      } else if (error.message.includes('500')) {
        errorMessage = '服务器内部错误，请稍后重试';
      }
      showToast(errorMessage);
      setGeneratingChapter(false);
    }
  };

  // 初始化页面数据
  useEffect(() => {
    const loadData = async () => {
      if (!novelId) return;

      try {
        setLoading(true);

        // 加载小说信息
        console.log('📚 加载小说信息...');
        const novelData = await NovelApi.getNovelDetail(novelId);
        setNovel(novelData);
        console.log('✅ 小说信息加载完成:', novelData);

        // 加载最新章节
        console.log('📖 加载最新章节...');
        const latestChapter = await ChapterApi.getLatestChapter(novelId);
        if (latestChapter) {
          setCurrentChapter(latestChapter);
          console.log('✅ 最新章节加载完成:', latestChapter);
        }

      } catch (error) {
        console.error('❌ 加载数据失败:', error);
        setError('加载失败，请重试');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [novelId]);

  // 清理函数
  useEffect(() => {
    return () => {
      if (sseControllerRef.current) {
        console.log('🧹 清理轮询连接');
        if (sseControllerRef.current.controller) {
          sseControllerRef.current.controller.abort();
        }
        if (sseControllerRef.current.intervalId) {
          clearInterval(sseControllerRef.current.intervalId);
        }
      }
    };
  }, []);

  if (loading) {
    return (
      <div style={{ padding: '20px' }}>
        <button onClick={() => navigate('/novels')}>← 返回列表</button>
        <h1>加载中...</h1>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '20px' }}>
        <button onClick={() => navigate('/novels')}>← 返回列表</button>
        <h1>加载失败</h1>
        <p>{error}</p>
        <button onClick={() => window.location.reload()}>重试</button>
      </div>
    );
  }

  if (!novel) {
    return (
      <div style={{ padding: '20px' }}>
        <button onClick={() => navigate('/novels')}>← 返回列表</button>
        <h1>小说不存在</h1>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', maxWidth: '800px', margin: '0 auto' }}>
      <button onClick={() => navigate('/novels')}>← 返回列表</button>
      <h1>{novel.title}</h1>

      {currentChapter ? (
        <div style={{ marginTop: '20px' }}>
          <h2>{currentChapter.title || '章节标题'}</h2>
          {currentChapter.isStreaming && (
            <p style={{ color: 'blue' }}>✨ AI正在创作中...</p>
          )}

          <div style={{
            whiteSpace: 'pre-wrap',
            lineHeight: '1.6',
            marginBottom: '20px',
            border: '1px solid #ddd',
            padding: '15px',
            borderRadius: '5px'
          }}>
            {currentChapter.content || (currentChapter.isStreaming ? '生成中...' : '暂无内容')}
            {currentChapter.isStreaming && <span style={{ animation: 'blink 1s infinite' }}>|</span>}
          </div>

          {!currentChapter.isStreaming && currentChapter.options && currentChapter.options.length > 0 && (
            <div>
              <h3>选择你的行动：</h3>
              {currentChapter.options.map((option, index) => (
                <div
                  key={option.id || index}
                  style={{
                    margin: '10px 0',
                    padding: '10px',
                    border: `2px solid ${selectedOption?.id === option.id ? '#007bff' : '#ddd'}`,
                    borderRadius: '5px',
                    cursor: 'pointer',
                    backgroundColor: selectedOption?.id === option.id ? '#e7f3ff' : 'white'
                  }}
                  onClick={() => setSelectedOption(option)}
                >
                  <strong>{index + 1}. {option.option_text}</strong>
                  {option.impact_description && (
                    <p style={{ margin: '5px 0 0 0', fontSize: '0.9em', color: '#666' }}>
                      💡 {option.impact_description}
                    </p>
                  )}
                </div>
              ))}

              <button
                onClick={() => selectedOption && handleOptionSelect(selectedOption)}
                disabled={generatingChapter || !selectedOption}
                style={{
                  marginTop: '15px',
                  padding: '10px 20px',
                  backgroundColor: selectedOption && !generatingChapter ? '#007bff' : '#ccc',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: selectedOption && !generatingChapter ? 'pointer' : 'not-allowed'
                }}
              >
                {generatingChapter ? '⚡ 正在生成下一章...' : !selectedOption ? '请先选择选项' : '✨ 确认选择并继续'}
              </button>
            </div>
          )}
        </div>
      ) : (
        <div style={{ marginTop: '20px', textAlign: 'center' }}>
          <h2>开始你的冒险</h2>
          <p>这部小说还没有章节，点击下方按钮开始生成第一章。</p>
          <button
            onClick={handleGenerateFirstChapter}
            disabled={generatingChapter}
            style={{
              padding: '10px 20px',
              backgroundColor: generatingChapter ? '#ccc' : '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '5px',
              cursor: generatingChapter ? 'not-allowed' : 'pointer'
            }}
          >
            {generatingChapter ? '⚡ 正在生成第一章...' : '🚀 开始生成第一章'}
          </button>
        </div>
      )}

      <style>
        {`
          @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0; }
          }
        `}
      </style>
    </div>
  );
};

export default ReadingPage;