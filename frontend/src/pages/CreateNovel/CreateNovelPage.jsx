import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { NovelApi } from '../../services/api';
import '../../styles/CreateNovelPage.css';

const CreateNovelPage = () => {
  const navigate = useNavigate();
  const [selectedGenre, setSelectedGenre] = useState('');
  const [additionalRequirements, setAdditionalRequirements] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [showResult, setShowResult] = useState(false);
  const [createdNovel, setCreatedNovel] = useState(null);

  const genres = [
    {
      id: 'wuxia',
      name: '武侠小说',
      icon: '⚔️',
      description: '江湖恩怨，武功秘籍，侠客豪情',
      features: ['武功体系', '江湖门派', '武侠世界观', '恩怨情仇']
    },
    {
      id: 'scifi',
      name: '科幻小说',
      icon: '🚀',
      description: '未来科技，星际探索，科学幻想',
      features: ['未来科技', '太空冒险', '外星文明', '科学设定']
    }
  ];

  const showToast = (message) => {
    const toast = document.createElement('div');
    toast.className = 'custom-toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
      document.body.removeChild(toast);
    }, 3000);
  };

  const handleCreateNovel = async () => {
    if (!selectedGenre) {
      showToast('请选择小说类型');
      return;
    }

    setIsCreating(true);
    try {
      console.log('开始创建小说:', { genre: selectedGenre, additional_requirements: additionalRequirements });

      const result = await NovelApi.createNovel({
        genre: selectedGenre,
        additional_requirements: additionalRequirements || ''
      });

      console.log('小说创建成功:', result);
      setCreatedNovel(result);
      setShowResult(true);
      showToast('小说创建成功！');

    } catch (error) {
      console.error('创建小说失败:', error);
      showToast('创建失败，请重试');
    } finally {
      setIsCreating(false);
    }
  };

  const handleStartReading = () => {
    navigate(`/novels/${createdNovel.novel_id}`);
  };

  const handleBackToList = () => {
    navigate('/novels');
  };

  if (showResult && createdNovel) {
    const generatedContent = createdNovel.generated_content;

    return (
      <div className="create-novel-page">
        <nav className="custom-navbar">
          <button
            className="nav-back-btn"
            onClick={handleBackToList}
          >
            ←
          </button>
          <h1>创建成功</h1>
        </nav>

        <div className="result-content">
          <div className="success-header">
            <div className="success-icon">🎉</div>
            <h2>小说创建成功！</h2>
            <p>AI已经为你生成了完整的小说设定</p>
          </div>

          <div className="novel-preview">
            <div className="preview-header">
              <div className="genre-badge">
                {selectedGenre === 'wuxia' ? '⚔️ 武侠' : '🚀 科幻'}
              </div>
              <h3 className="novel-title">{generatedContent.title}</h3>
            </div>

            <div className="preview-section">
              <h4>📝 故事简介</h4>
              <p className="novel-summary">{generatedContent.summary}</p>
            </div>

            <div className="preview-section">
              <h4>🌍 世界观设定</h4>
              <div className="world-setting">
                <p><strong>背景：</strong>{generatedContent.world_setting.background}</p>
                {selectedGenre === 'wuxia' ? (
                  <>
                    <p><strong>朝代：</strong>{generatedContent.world_setting.dynasty}</p>
                    <p><strong>武功体系：</strong>{generatedContent.world_setting.martial_arts_system}</p>
                    <p><strong>主要门派：</strong>{generatedContent.world_setting.major_sects?.join('、')}</p>
                  </>
                ) : (
                  <>
                    <p><strong>科技水平：</strong>{generatedContent.world_setting.technology_level}</p>
                    <p><strong>太空设定：</strong>{generatedContent.world_setting.space_setting}</p>
                    <p><strong>外星种族：</strong>{generatedContent.world_setting.alien_races?.join('、')}</p>
                  </>
                )}
              </div>
            </div>

            <div className="preview-section">
              <h4>🎭 主角设定</h4>
              <div className="protagonist-info">
                <p><strong>姓名：</strong>{generatedContent.protagonist.name}</p>
                <p><strong>性格：</strong>{generatedContent.protagonist.personality}</p>
                <p><strong>背景：</strong>{generatedContent.protagonist.background}</p>
                <p><strong>动机：</strong>{generatedContent.protagonist.motivation}</p>
              </div>
            </div>
          </div>

          <div className="result-actions">
            <button
              className="primary-btn"
              onClick={handleStartReading}
            >
              开始阅读
            </button>
            <button
              className="secondary-btn"
              onClick={() => navigate('/novels')}
            >
              返回列表
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="create-novel-page">
      <nav className="custom-navbar">
        <button
          className="nav-back-btn"
          onClick={() => navigate('/novels')}
        >
          ←
        </button>
        <h1>创建新小说</h1>
      </nav>

      <div className="create-content">
        <div className="create-header">
          <div className="header-icon">✨</div>
          <h2>AI智能创作</h2>
          <p>选择小说类型，AI将为你生成独特的故事世界</p>
        </div>

        <div className="genre-selection">
          <h3>选择小说类型</h3>
          <div className="genre-grid">
            {genres.map((genre) => (
              <div
                key={genre.id}
                className={`genre-card ${selectedGenre === genre.id ? 'selected' : ''}`}
                onClick={() => setSelectedGenre(genre.id)}
              >
                <div className="genre-icon">{genre.icon}</div>
                <h4 className="genre-name">{genre.name}</h4>
                <p className="genre-description">{genre.description}</p>
                <div className="genre-features">
                  {genre.features.map((feature, index) => (
                    <span key={index} className="feature-tag">{feature}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="requirements-section">
          <h3>额外要求 <span className="optional">(可选)</span></h3>
          <textarea
            className="requirements-input"
            placeholder="例如：希望主角是一个年轻的剑客，故事发生在江南..."
            value={additionalRequirements}
            onChange={(e) => setAdditionalRequirements(e.target.value)}
            maxLength={500}
          />
          <div className="char-count">
            {additionalRequirements.length}/500
          </div>
        </div>

        <div className="create-actions">
          <button
            className="create-btn"
            onClick={handleCreateNovel}
            disabled={!selectedGenre || isCreating}
          >
            {isCreating ? (
              <>
                <span className="loading-spinner">⚡</span>
                AI正在创作中...
              </>
            ) : (
              '✨ 开始创作'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default CreateNovelPage;