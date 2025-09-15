import { createBrowserRouter, Navigate } from 'react-router-dom';

// 页面组件（稍后创建）
import SplashScreen from './pages/SplashScreen';
import LoginPage from './pages/Login/LoginPage';
import RegisterPage from './pages/Register/RegisterPage';
import HomePage from './pages/Home/HomePage';
import NovelListPage from './pages/NovelList/NovelListPage';
import CreateNovelPage from './pages/CreateNovel/CreateNovelPage';
import ReadingPage from './pages/Reading/ReadingPage';
import ProfilePage from './pages/Profile/ProfilePage';
import NotFoundPage from './pages/NotFound/NotFoundPage';

// 认证守卫组件
const AuthGuard = ({ children }) => {
  const token = localStorage.getItem('access_token');

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

// 路由配置
export const router = createBrowserRouter([
  // 启动页
  {
    path: '/',
    element: <SplashScreen />
  },

  // 认证相关路由
  {
    path: '/login',
    element: <LoginPage />
  },
  {
    path: '/register',
    element: <RegisterPage />
  },

  // 主应用路由（需要认证）
  {
    path: '/home',
    element: (
      <AuthGuard>
        <HomePage />
      </AuthGuard>
    )
  },
  {
    path: '/novels',
    element: (
      <AuthGuard>
        <NovelListPage />
      </AuthGuard>
    )
  },
  {
    path: '/create',
    element: (
      <AuthGuard>
        <CreateNovelPage />
      </AuthGuard>
    )
  },
  {
    path: '/novels/:id',
    element: (
      <AuthGuard>
        <ReadingPage />
      </AuthGuard>
    )
  },
  {
    path: '/novels/:id/chapters/:chapterId',
    element: (
      <AuthGuard>
        <ReadingPage />
      </AuthGuard>
    )
  },
  {
    path: '/novels/:id/generate',
    element: (
      <AuthGuard>
        <ReadingPage />
      </AuthGuard>
    )
  },
  {
    path: '/profile',
    element: (
      <AuthGuard>
        <ProfilePage />
      </AuthGuard>
    )
  },

  // 404 页面
  {
    path: '*',
    element: <NotFoundPage />
  }
]);

export default router;