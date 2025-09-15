import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { SpinLoading } from 'antd-mobile';
import '../styles/SplashScreen.css';

const SplashScreen = () => {
  const navigate = useNavigate();
  const { user, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading) {
      // 认证检查完成后跳转
      if (user) {
        navigate('/home', { replace: true });
      } else {
        navigate('/login', { replace: true });
      }
    }
  }, [user, isLoading, navigate]);

  return (
    <div className="splash-screen">
      <div className="splash-content">
        <div className="logo">
          🤖
        </div>
        <h1 className="title">AI互动小说</h1>
        <p className="subtitle">你的选择决定故事走向</p>
        <div className="loading">
          <SpinLoading color="primary" />
          <p>加载中...</p>
        </div>
      </div>
    </div>
  );
};

export default SplashScreen;