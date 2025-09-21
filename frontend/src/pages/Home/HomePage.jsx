import { useAuth } from '../../contexts/AuthContext';
import { Button, Space } from 'antd-mobile';
import { useNavigate } from 'react-router-dom';
import { Transition } from '@headlessui/react';
import { useState, useEffect } from 'react';
import '../../styles/HomePage.css';

const HomePage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    setIsVisible(true);
  }, []);

  // 简单的机器人图标
  const RobotIcon = () => (
    <div className="logo">🤖</div>
  );

  // 移除复杂的装饰组件

  return (
    <div className="home-page">
      {/* 移除复杂的背景元素 */}
      
      {/* Header */}
      <Transition
        show={isVisible}
        enter="transition-all duration-1000 ease-out"
        enterFrom="opacity-0 -translate-y-8"
        enterTo="opacity-100 translate-y-0"
      >
        <div className="home-header">
          <div className="user-info">
            <div className="user-avatar">
              {(user?.name || '用户').charAt(0).toUpperCase()}
            </div>
            <span>欢迎回来，{user?.name || '用户'}</span>
          </div>
          <div className="settings-btn" onClick={() => navigate('/profile')}>
            <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">
              <path d="M19.14,12.94c0.04-0.3,0.06-0.61,0.06-0.94c0-0.32-0.02-0.64-0.07-0.94l2.03-1.58c0.18-0.14,0.23-0.41,0.12-0.61 l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39,0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4,2.81c-0.04-0.24-0.24-0.41-0.48-0.41 h-3.84c-0.24,0-0.43,0.17-0.47,0.41L9.25,5.35C8.66,5.59,8.12,5.92,7.63,6.29L5.24,5.33c-0.22-0.08-0.47,0-0.59,0.22L2.74,8.87 C2.62,9.08,2.66,9.34,2.86,9.48l2.03,1.58C4.84,11.36,4.82,11.69,4.82,12s0.02,0.64,0.07,0.94l-2.03,1.58 c-0.18,0.14-0.23,0.41-0.12,0.61l1.92,3.32c0.12,0.22,0.37,0.29,0.59,0.22l2.39-0.96c0.5,0.38,1.03,0.7,1.62,0.94l0.36,2.54 c0.05,0.24,0.24,0.41,0.48,0.41h3.84c0.24,0,0.44-0.17,0.47-0.41l0.36-2.54c0.59-0.24,1.13-0.56,1.62-0.94l2.39,0.96 c0.22,0.08,0.47,0,0.59-0.22l1.92-3.32c0.12-0.22,0.07-0.47-0.12-0.61L19.14,12.94z M12,15.6c-1.98,0-3.6-1.62-3.6-3.6 s1.62-3.6,3.6-3.6s3.6,1.62,3.6,3.6S13.98,15.6,12,15.6z"/>
            </svg>
          </div>
        </div>
      </Transition>

      {/* Main Content */}
      <div className="home-content">
        <Transition
          show={isVisible}
          enter="transition-all duration-1500 ease-out delay-300"
          enterFrom="opacity-0 scale-95 translate-y-8"
          enterTo="opacity-100 scale-100 translate-y-0"
        >
          <div className="hero-section">
            <RobotIcon />
            <h1 className="hero-title">
              <span className="title-word">AI</span>
              <span className="title-word">互动</span>
              <span className="title-word">小说</span>
            </h1>
            <p className="hero-subtitle">你的选择决定故事走向</p>
            <div className="subtitle-decoration" />
          </div>
        </Transition>

        <Transition
          show={isVisible}
          enter="transition-all duration-1000 ease-out delay-700"
          enterFrom="opacity-0 translate-y-8"
          enterTo="opacity-100 translate-y-0"
        >
          <div className="action-buttons">
            <button
              className="primary-action-btn"
              onClick={() => navigate('/novels')}
            >
              <div className="btn-content">
                <svg className="btn-icon" viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                  <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>
                </svg>
                <span>我的小说</span>
              </div>
              <div className="btn-ripple" />
            </button>
            
            <button
              className="secondary-action-btn"
              onClick={() => navigate('/create')}
            >
              <div className="btn-content">
                <svg className="btn-icon" viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                  <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
                </svg>
                <span>创建新小说</span>
              </div>
              <div className="btn-ripple" />
            </button>
          </div>
        </Transition>
      </div>
    </div>
  );
};

export default HomePage;