import { NavBar } from 'antd-mobile';
import { LeftOutline } from 'antd-mobile-icons';
import { useNavigate } from 'react-router-dom';

const ReadingPage = () => {
  const navigate = useNavigate();

  return (
    <div>
      <NavBar
        onBack={() => navigate('/novels')}
        backArrow={<LeftOutline />}
      >
        小说阅读
      </NavBar>
      <div style={{ padding: '1rem', textAlign: 'center' }}>
        <h2>阅读页面</h2>
        <p>功能开发中...</p>
      </div>
    </div>
  );
};

export default ReadingPage;