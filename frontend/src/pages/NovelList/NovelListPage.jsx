import { NavBar } from 'antd-mobile';
import { LeftOutline } from 'antd-mobile-icons';
import { useNavigate } from 'react-router-dom';

const NovelListPage = () => {
  const navigate = useNavigate();

  return (
    <div>
      <NavBar
        onBack={() => navigate('/home')}
        backArrow={<LeftOutline />}
      >
        我的小说
      </NavBar>
      <div style={{ padding: '1rem', textAlign: 'center' }}>
        <h2>小说列表页面</h2>
        <p>功能开发中...</p>
      </div>
    </div>
  );
};

export default NovelListPage;