// 在浏览器控制台中运行此代码来测试流式接口
// 1. 首先在浏览器中打开 http://localhost:8000
// 2. 打开开发者工具（F12）
// 3. 粘贴并运行下面的代码

async function testStreamingAPI() {
    try {
        // 1. 登录获取token
        console.log('🔐 正在登录...');
        const loginResponse = await fetch('http://localhost:8000/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: 'curltest@example.com',
                password: 'test123'
            })
        });

        if (!loginResponse.ok) {
            console.error('❌ 登录失败:', loginResponse.status);
            return;
        }

        const loginData = await loginResponse.json();
        const token = loginData.access_token;
        console.log('✅ 登录成功!');

        // 2. 创建章节生成任务
        console.log('📝 正在创建章节生成任务...');
        const taskResponse = await fetch('http://localhost:8000/api/v1/novels/1/chapters/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({})
        });

        if (!taskResponse.ok) {
            console.error('❌ 任务创建失败:', taskResponse.status);
            return;
        }

        const taskData = await taskResponse.json();
        const taskId = taskData.task_id;
        console.log('✅ 任务创建成功，任务ID:', taskId);

        // 3. 连接流式接口
        console.log('🌊 正在连接流式接口...');
        const streamUrl = `http://localhost:8000/api/v1/novels/1/chapters/generate/${taskId}/stream`;

        const eventSource = new EventSource(streamUrl + `?token=${encodeURIComponent(token)}`);

        eventSource.onopen = function() {
            console.log('🔗 流式连接已建立!');
        };

        eventSource.addEventListener('progress', function(e) {
            const data = JSON.parse(e.data);
            console.log('📊 进度更新:', `${data.progress}% - ${data.step}`);
        });

        eventSource.addEventListener('content', function(e) {
            const data = JSON.parse(e.data);
            console.log('📝 内容片段:', data.text);
        });

        eventSource.addEventListener('complete', function(e) {
            const data = JSON.parse(e.data);
            console.log('🎉 生成完成!', data);
            eventSource.close();
        });

        eventSource.addEventListener('error', function(e) {
            const data = JSON.parse(e.data);
            console.error('❌ 错误:', data.error);
            eventSource.close();
        });

        eventSource.onerror = function(e) {
            console.error('❌ 连接错误', e);
            eventSource.close();
        };

        // 30秒后自动关闭连接
        setTimeout(() => {
            eventSource.close();
            console.log('⏰ 测试超时，连接已关闭');
        }, 30000);

    } catch (error) {
        console.error('❌ 测试异常:', error);
    }
}

// 运行测试
testStreamingAPI();