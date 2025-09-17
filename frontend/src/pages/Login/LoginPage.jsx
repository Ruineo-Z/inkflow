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
      // 使用原生alert作为临时解决方案
      alert('✅ 登录成功！');
      navigate('/home', { replace: true });
    } catch (error) {
      console.error('登录错误:', error);

      // 根据不同错误类型显示不同的提示信息
      let errorMessage = '登录失败，请检查邮箱和密码';

      if (error.message === 'Incorrect email or password') {
        errorMessage = '❌ 邮箱或密码错误，请重新输入';
      } else if (error.message.includes('email')) {
        errorMessage = '❌ 邮箱格式不正确';
      } else if (error.message.includes('password')) {
        errorMessage = '❌ 密码格式不正确';
      } else if (error.message) {
        errorMessage = `❌ ${error.message}`;
      }

      // 使用原生alert作为临时解决方案，因为Toast有React兼容性问题
      alert(errorMessage);

      // TODO: 等待Ant Design Mobile修复React 19兼容性后恢复Toast
      // Toast.show({
      //   content: errorMessage,
      //   position: 'top',
      //   duration: 4000
      // });
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