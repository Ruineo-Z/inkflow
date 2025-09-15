import { Button } from 'antd-mobile';
import { useNavigate } from 'react-router-dom';

const NotFoundPage = () => {
  const navigate = useNavigate();

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      textAlign: 'center',
      padding: '2rem'
    }}>
      <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>😕</div>
      <h1>页面未找到</h1>
      <p style={{ marginBottom: '2rem' }}>抱歉，您访问的页面不存在</p>
      <Button
        color="primary"
        onClick={() => navigate('/home', { replace: true })}
      >
        返回首页
      </Button>
    </div>
  );
};

export default NotFoundPage;