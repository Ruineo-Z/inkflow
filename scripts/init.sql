-- 创建数据库扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 创建时区扩展
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 设置时区
SET timezone = 'UTC';

-- 创建用户（如果不存在）
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'inkflow') THEN
        CREATE USER inkflow WITH PASSWORD 'inkflow123';
    END IF;
END
$$;

-- 授予用户权限
GRANT ALL PRIVILEGES ON DATABASE inkflow TO inkflow;
GRANT ALL ON SCHEMA public TO inkflow;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO inkflow;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO inkflow;

-- 默认授予未来创建的对象权限
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO inkflow;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO inkflow;