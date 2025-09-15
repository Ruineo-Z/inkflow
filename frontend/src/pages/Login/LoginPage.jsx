import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, Toast } from 'antd-mobile';
import { useAuth } from '../../contexts/AuthContext';
import '../../styles/AuthPages.css';

const LoginPage = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [form] = Form.useForm();

  const handleSubmit = async (values) => {
    setIsLoading(true);
    try {
      await login(values);
      Toast.show({ content: '登录成功！', position: 'top' });
      navigate('/home', { replace: true });
    } catch (error) {
      Toast.show({
        content: error.message || '登录失败，请检查邮箱和密码',
        position: 'top'
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-content">
        {/* 头部 */}
        <div className="auth-header">
          <div className="logo">🤖</div>
          <h1>AI互动小说</h1>
          <p>你的选择决定故事走向</p>
        </div>

        {/* 表单 */}
        <div className="auth-form">
          <h2>登录到你的账户</h2>

          <Form
            form={form}
            onFinish={handleSubmit}
            layout="vertical"
          >
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

            <Button
              block
              type="submit"
              color="primary"
              size="large"
              loading={isLoading}
            >
              登录
            </Button>
          </Form>

          {/* 注册链接 */}
          <div className="auth-footer">
            <span>还没有账户？</span>
            <Link to="/register">立即注册</Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;