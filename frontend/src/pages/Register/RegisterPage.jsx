import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, Toast, NavBar } from 'antd-mobile';
import { LeftOutline } from 'antd-mobile-icons';
import { useAuth } from '../../contexts/AuthContext';
import '../../styles/AuthPages.css';

const RegisterPage = () => {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [form] = Form.useForm();

  const handleSubmit = async (values) => {
    if (values.password !== values.confirmPassword) {
      Toast.show({ content: '两次输入的密码不一致', position: 'top' });
      return;
    }

    setIsLoading(true);
    try {
      const { confirmPassword, ...registerData } = values;
      await register(registerData);
      Toast.show({ content: '注册成功！', position: 'top' });
      navigate('/home', { replace: true });
    } catch (error) {
      Toast.show({
        content: error.message || '注册失败，请稍后重试',
        position: 'top'
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <NavBar
        onBack={() => navigate('/login')}
        backArrow={<LeftOutline />}
      >
        创建新账户
      </NavBar>

      <div className="auth-content">
        <div className="auth-form">
          <Form
            form={form}
            onFinish={handleSubmit}
            layout="vertical"
          >
            <Form.Item
              name="name"
              label="👤 用户名"
              rules={[
                { required: true, message: '请输入用户名' },
                { min: 2, message: '用户名至少2位' }
              ]}
            >
              <Input placeholder="请输入用户名" />
            </Form.Item>

            <Form.Item
              name="email"
              label="📧 邮箱地址"
              rules={[
                { required: true, message: '请输入邮箱地址' },
                { type: 'email', message: '请输入有效的邮箱地址' }
              ]}
            >
              <Input placeholder="user@example.com" />
            </Form.Item>

            <Form.Item
              name="password"
              label="🔒 密码"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 6, message: '密码至少6位' }
              ]}
            >
              <Input type="password" placeholder="请输入密码" />
            </Form.Item>

            <Form.Item
              name="confirmPassword"
              label="🔒 确认密码"
              rules={[
                { required: true, message: '请确认密码' }
              ]}
            >
              <Input type="password" placeholder="请再次输入密码" />
            </Form.Item>

            <Button
              block
              type="submit"
              color="primary"
              size="large"
              loading={isLoading}
            >
              创建账户
            </Button>
          </Form>

          {/* 登录链接 */}
          <div className="auth-footer">
            <span>已有账户？</span>
            <Link to="/login">返回登录</Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;