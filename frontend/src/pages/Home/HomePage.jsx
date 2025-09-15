import { useAuth } from '../../contexts/AuthContext';
import { Button, Space } from 'antd-mobile';
import { useNavigate } from 'react-router-dom';
import '../../styles/HomePage.css';

const HomePage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="home-page">
      <div className="home-header">
        <div className="user-info">
          <span>👤 {user?.name}</span>
        </div>
        <div className="settings-btn" onClick={() => navigate('/profile')}>
          ⚙️
        </div>
      </div>

      <div className="home-content">
        <div className="hero-section">
          <div className="logo">🤖</div>
          <h1>AI互动小说</h1>
          <p>你的选择决定故事走向</p>
        </div>

        <div className="action-buttons">
          <Space direction="vertical" block>
            <Button
              block
              color="primary"
              size="large"
              onClick={() => navigate('/novels')}
            >
              我的小说
            </Button>
            <Button
              block
              color="default"
              size="large"
              onClick={() => navigate('/create')}
            >
              创建新小说
            </Button>
          </Space>
        </div>
      </div>
    </div>
  );
};

export default HomePage;