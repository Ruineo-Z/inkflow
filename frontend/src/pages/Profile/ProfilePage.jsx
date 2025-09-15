import { NavBar, Button, Toast } from 'antd-mobile';
import { LeftOutline } from 'antd-mobile-icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

const ProfilePage = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    Toast.show({ content: '已退出登录', position: 'top' });
    navigate('/login', { replace: true });
  };

  return (
    <div>
      <NavBar
        onBack={() => navigate('/home')}
        backArrow={<LeftOutline />}
      >
        个人中心
      </NavBar>
      <div style={{ padding: '1rem' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>👤</div>
          <h2>{user?.name}</h2>
          <p>{user?.email}</p>
        </div>

        <Button
          block
          color="danger"
          onClick={handleLogout}
        >
          退出登录
        </Button>
      </div>
    </div>
  );
};

export default ProfilePage;