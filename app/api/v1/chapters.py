import json
import logging
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.security import get_current_user_id, create_resume_token, verify_resume_token
from app.services.chapter import ChapterService
from app.services.chapter_generator import chapter_generator
from app.services.novel import NovelService
from app.services.stream_manager import StreamGenerationManager, managed_stream_generation
from app.services.chapter_cache import ChapterCacheService
from app.models.chapter import ChapterStatus
from app.schemas.chapter import (
    GenerateChapterRequest,
    SaveUserChoiceRequest,
    ChapterResponse,
    UserChoiceResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/novels/{novel_id}/chapters/generate", summary="生成章节内容（流式）")
async def generate_chapter_stream(
    novel_id: int,
    request: GenerateChapterRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    生成章节内容的流式接口

    - 第一章：selected_option_id为null
    - 后续章节：传入上一章选择的option_id

    返回Server-Sent Events (SSE)流式数据：
    - event: status - 生成状态信息
    - event: summary - 章节摘要
    - event: content - 章节内容片段
    - event: complete - 生成完成，包含完整数据
    - event: error - 错误信息
    """
    try:
        # 1. 验证小说存在且属于当前用户
        novel_service = NovelService(db)
        novel = await novel_service.get_by_id(novel_id)

        if not novel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="小说不存在"
            )

        if novel.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此小说"
            )

        # 2. 初始化服务
        chapter_service = ChapterService(db)

        # 3. 判断是第一章还是后续章节
        latest_chapter_num = await chapter_service.get_latest_chapter_number(novel_id)

        if latest_chapter_num == 0:
            # 第一章生成

            async def first_chapter_stream():
                chapter_id = None
                session_id = None
                stream_manager = None

                try:
                    async for event_data in chapter_generator.generate_first_chapter_stream(
                        world_setting=novel.background_setting or "",
                        protagonist_info=novel.character_setting or "",
                        genre=novel.theme or "wuxia"
                    ):
                        # 解析事件数据
                        if event_data.startswith("event: summary"):
                            # 提取摘要数据并创建章节记录
                            data_line = event_data.split('\n')[1]
                            summary_data = json.loads(data_line.split('data: ')[1])

                            # 创建章节记录
                            from app.schemas.chapter import ChapterSummary
                            summary = ChapterSummary(**summary_data)
                            chapter = await chapter_service.create_chapter_with_summary(
                                novel_id=novel_id,
                                chapter_number=1,
                                summary_data=summary
                            )
                            chapter_id = chapter.id

                            # 初始化StreamGenerationManager
                            session_id = StreamGenerationManager.generate_session_id()
                            stream_manager = StreamGenerationManager(
                                chapter_id=chapter_id,
                                novel_id=novel_id,
                                session_id=session_id,
                                db=db
                            )
                            await stream_manager.start_generation(title=summary.title)

                            # 生成并发送resume_token
                            resume_token = create_resume_token(
                                chapter_id=chapter_id,
                                session_id=session_id,
                                novel_id=novel_id,
                                user_id=current_user_id,
                                sent_length=0
                            )

                            # 发送resume_token事件
                            yield f"event: resume_token\ndata: {json.dumps({'resume_token': resume_token, 'chapter_id': chapter_id, 'session_id': session_id})}\n\n"

                        elif event_data.startswith("event: content") and stream_manager:
                            # 提取内容chunk并写入Redis
                            data_line = event_data.split('\n')[1]
                            content_data = json.loads(data_line.split('data: ')[1])
                            chunk_text = content_data['text']

                            # 追加到StreamManager (自动写Redis + 定时同步PostgreSQL)
                            await stream_manager.append_chunk(chunk_text)

                        elif event_data.startswith("event: complete") and chapter_id and stream_manager:
                            # 提取完整数据并最终保存
                            data_line = event_data.split('\n')[1]
                            complete_data = json.loads(data_line.split('data: ')[1])

                            # 完成生成 (最终写PostgreSQL + 清理Redis)
                            await stream_manager.complete_generation(
                                final_content=complete_data["content"],
                                options=complete_data["options"]
                            )

                            # 添加章节ID到返回数据
                            complete_data["chapter_id"] = chapter_id
                            yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
                            continue

                        yield event_data

                except Exception as e:
                    logger.error(f"❌ 第一章生成失败: {e}")
                    # 标记失败
                    if stream_manager:
                        try:
                            await stream_manager.fail_generation(str(e))
                        except Exception as cleanup_error:
                            logger.error(f"❌ 清理失败状态时出错: {cleanup_error}")

                    yield f"event: error\ndata: {json.dumps({'error': f'生成失败: {str(e)}'})}\n\n"

            return StreamingResponse(
                first_chapter_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                }
            )

        else:
            # 后续章节生成

            async def next_chapter_stream():
                chapter_id = None
                session_id = None
                stream_manager = None

                try:
                    # 获取用户最新选择
                    selected_option_id = await chapter_service.get_latest_user_choice(
                        user_id=current_user_id,
                        novel_id=novel_id
                    )

                    if not selected_option_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="未找到用户选择，请先选择一个选项"
                        )

                    logger.info(f"🎯 从数据库获取用户选择: {selected_option_id}")

                    # 获取生成上下文
                    context = await chapter_service.get_generation_context(
                        novel_id, selected_option_id
                    )

                    # 获取下一章节号
                    next_chapter_num = await chapter_service.get_latest_chapter_number(novel_id) + 1

                    async for event_data in chapter_generator.generate_next_chapter_stream(
                        novel_id, selected_option_id, context
                    ):
                        # 类似第一章的处理逻辑
                        if event_data.startswith("event: summary"):
                            # 创建章节记录
                            data_line = event_data.split('\n')[1]
                            summary_data = json.loads(data_line.split('data: ')[1])

                            from app.schemas.chapter import ChapterSummary
                            summary = ChapterSummary(**summary_data)
                            chapter = await chapter_service.create_chapter_with_summary(
                                novel_id=novel_id,
                                chapter_number=next_chapter_num,
                                summary_data=summary
                            )
                            chapter_id = chapter.id

                            # 初始化StreamGenerationManager
                            session_id = StreamGenerationManager.generate_session_id()
                            stream_manager = StreamGenerationManager(
                                chapter_id=chapter_id,
                                novel_id=novel_id,
                                session_id=session_id,
                                db=db
                            )
                            await stream_manager.start_generation(title=summary.title)

                            # 生成并发送resume_token
                            resume_token = create_resume_token(
                                chapter_id=chapter_id,
                                session_id=session_id,
                                novel_id=novel_id,
                                user_id=current_user_id,
                                sent_length=0
                            )

                            # 发送resume_token事件
                            yield f"event: resume_token\ndata: {json.dumps({'resume_token': resume_token, 'chapter_id': chapter_id, 'session_id': session_id})}\n\n"

                        elif event_data.startswith("event: content") and stream_manager:
                            # 提取内容chunk并写入Redis
                            data_line = event_data.split('\n')[1]
                            content_data = json.loads(data_line.split('data: ')[1])
                            chunk_text = content_data['text']

                            # 追加到StreamManager (自动写Redis + 定时同步PostgreSQL)
                            await stream_manager.append_chunk(chunk_text)

                        elif event_data.startswith("event: complete") and chapter_id and stream_manager:
                            data_line = event_data.split('\n')[1]
                            complete_data = json.loads(data_line.split('data: ')[1])

                            # 完成生成 (最终写PostgreSQL + 清理Redis)
                            await stream_manager.complete_generation(
                                final_content=complete_data["content"],
                                options=complete_data["options"]
                            )

                            complete_data["chapter_id"] = chapter_id
                            yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
                            continue

                        yield event_data

                except Exception as e:
                    logger.error(f"❌ 后续章节生成失败: {e}")
                    # 标记失败
                    if stream_manager:
                        try:
                            await stream_manager.fail_generation(str(e))
                        except Exception as cleanup_error:
                            logger.error(f"❌ 清理失败状态时出错: {cleanup_error}")

                    yield f"event: error\ndata: {json.dumps({'error': f'生成失败: {str(e)}'})}\n\n"

            return StreamingResponse(
                next_chapter_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"章节生成失败: {str(e)}"
        )


@router.post("/novels/{novel_id}/chapters/reconnect", summary="重连章节生成（断线重连）")
async def reconnect_chapter_generation(
    novel_id: int,
    resume_token: str,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    重连章节生成接口（断线重连）

    前端使用localStorage保存的resume_token请求重连,
    后端计算差异内容并流式发送。

    流程:
    1. 验证resume_token (签名、用户、有效期、session_id)
    2. 优先从Redis读取当前内容
    3. Redis未命中则从PostgreSQL读取
    4. 计算差异: new_content = current_content[sent_length:]
    5. 流式发送差异内容 (分chunk模拟打字机效果)
    6. 检查状态: completed → 发送complete事件

    Returns:
        StreamingResponse: SSE流
            - event: status - 重连状态
            - event: content - 差异内容片段
            - event: complete - 生成已完成
            - event: generating - 仍在生成中
            - event: error - 错误信息
    """
    try:
        # 1. 验证resume_token
        payload = verify_resume_token(resume_token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效或过期的resume_token"
            )

        # 2. 验证用户权限
        token_user_id = payload["user_id"]
        token_chapter_id = payload["chapter_id"]
        token_novel_id = payload["novel_id"]
        token_session_id = payload["session_id"]
        sent_length = payload["sent_length"]

        if token_user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此章节"
            )

        if token_novel_id != novel_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="novel_id不匹配"
            )

        logger.info(f"🔄 重连请求: chapter={token_chapter_id}, session={token_session_id}, sent_length={sent_length}")

        # 3. 定义重连流式生成器
        async def reconnect_stream():
            try:
                # 3.1 优先从Redis读取
                cached_data = await ChapterCacheService.get_generating_content(token_chapter_id)

                if cached_data:
                    # Redis命中
                    current_content = cached_data["content"]
                    current_length = cached_data["content_length"]
                    chapter_title = cached_data["title"]

                    # 验证session_id匹配
                    if cached_data["session_id"] != token_session_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="session_id不匹配，可能是新的生成会话"
                        )

                    logger.info(f"✅ Redis命中: chapter={token_chapter_id}, current_length={current_length}")

                else:
                    # 3.2 Redis未命中，从PostgreSQL读取
                    chapter_service = ChapterService(db)
                    chapter = await chapter_service.get_chapter_by_id(token_chapter_id)

                    if not chapter:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="章节不存在"
                        )

                    current_content = chapter.content or ""
                    current_length = chapter.content_length or 0
                    chapter_title = chapter.title

                    # 验证session_id (如果PostgreSQL中有记录)
                    if chapter.session_id and chapter.session_id != token_session_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="session_id不匹配，可能是新的生成会话"
                        )

                    logger.info(f"✅ PostgreSQL命中: chapter={token_chapter_id}, current_length={current_length}")

                # 4. 计算差异内容
                if sent_length >= current_length:
                    # 没有新内容
                    yield f"event: status\ndata: {json.dumps({'message': '已是最新内容'})}\n\n"

                    # 检查章节状态
                    chapter_status = await ChapterCacheService.get_status(token_chapter_id)
                    if not chapter_status:
                        # Redis中没有状态，从PostgreSQL读取
                        chapter_service = ChapterService(db)
                        chapter = await chapter_service.get_chapter_by_id(token_chapter_id)
                        chapter_status = chapter.status if chapter else ChapterStatus.COMPLETED

                    if chapter_status == ChapterStatus.COMPLETED:
                        yield f"event: complete\ndata: {json.dumps({'message': '章节已完成生成'})}\n\n"
                    elif chapter_status == ChapterStatus.GENERATING:
                        yield f"event: generating\ndata: {json.dumps({'message': '仍在生成中，请稍后重试'})}\n\n"
                    elif chapter_status == ChapterStatus.FAILED:
                        yield f"event: error\ndata: {json.dumps({'error': '章节生成失败'})}\n\n"

                    return

                # 5. 流式发送差异内容 (分chunk模拟打字机效果)
                diff_content = current_content[sent_length:]
                logger.info(f"📤 发送差异内容: {len(diff_content)} 字符")

                yield f"event: status\ndata: {json.dumps({'message': f'正在发送 {len(diff_content)} 字符的新内容...'})}\n\n"

                # 每5个字符一个chunk (模拟流式效果)
                chunk_size = 5
                for i in range(0, len(diff_content), chunk_size):
                    chunk = diff_content[i:i+chunk_size]
                    yield f"event: content\ndata: {json.dumps({'text': chunk})}\n\n"

                # 6. 检查生成状态
                chapter_status = await ChapterCacheService.get_status(token_chapter_id)
                if not chapter_status:
                    # Redis中没有状态，从PostgreSQL读取
                    chapter_service = ChapterService(db)
                    chapter = await chapter_service.get_chapter_by_id(token_chapter_id)
                    chapter_status = chapter.status if chapter else ChapterStatus.COMPLETED

                if chapter_status == ChapterStatus.COMPLETED:
                    # 生成已完成，发送complete事件 (包含选项)
                    chapter_service = ChapterService(db)
                    chapter = await chapter_service.get_chapter_by_id(token_chapter_id)

                    options_data = [
                        {
                            "text": opt.text,
                            "impact_hint": opt.impact_hint,
                            "tags": opt.tags
                        }
                        for opt in chapter.options
                    ] if chapter and chapter.options else []

                    yield f"event: complete\ndata: {json.dumps({'message': '章节已完成', 'chapter_id': token_chapter_id, 'title': chapter_title, 'content': current_content, 'options': options_data})}\n\n"

                elif chapter_status == ChapterStatus.GENERATING:
                    # 仍在生成中
                    yield f"event: generating\ndata: {json.dumps({'message': '章节仍在生成中', 'current_length': current_length})}\n\n"

                elif chapter_status == ChapterStatus.FAILED:
                    # 生成失败
                    yield f"event: error\ndata: {json.dumps({'error': '章节生成失败'})}\n\n"

            except HTTPException as he:
                yield f"event: error\ndata: {json.dumps({'error': he.detail})}\n\n"
            except Exception as e:
                logger.error(f"❌ 重连失败: {e}")
                yield f"event: error\ndata: {json.dumps({'error': f'重连失败: {str(e)}'})}\n\n"

        return StreamingResponse(
            reconnect_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重连失败: {str(e)}"
        )


@router.post("/chapters/{chapter_id}/choice", response_model=UserChoiceResponse, summary="保存用户选择")
async def save_user_choice(
    chapter_id: int,
    request: SaveUserChoiceRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    保存用户在特定章节的选择
    """
    try:
        chapter_service = ChapterService(db)

        # 1. 验证章节存在
        chapter = await chapter_service.get_chapter_by_id(chapter_id)
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="章节不存在"
            )

        # 2. 验证用户权限（通过小说验证）
        novel_service = NovelService(db)
        novel = await novel_service.get_by_id(chapter.novel_id)
        if not novel or novel.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此章节"
            )

        # 3. 验证选项存在
        option_exists = False
        for option in chapter.options:
            if option.id == request.option_id:
                option_exists = True
                break

        if not option_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="选项不存在"
            )

        # 4. 保存用户选择
        try:
            choice = await chapter_service.save_user_choice(
                user_id=current_user_id,
                chapter_id=chapter_id,
                option_id=request.option_id
            )

            return UserChoiceResponse.from_orm(choice)

        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存选择失败: {str(e)}"
        )


@router.get("/novels/{novel_id}/chapters", response_model=list[ChapterResponse], summary="获取小说章节列表")
async def get_novel_chapters(
    novel_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    获取小说的所有章节列表
    """
    try:
        # 验证小说权限
        novel_service = NovelService(db)
        novel = await novel_service.get_by_id(novel_id)

        if not novel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="小说不存在"
            )

        if novel.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此小说"
            )

        # 获取章节列表（包含用户选择）
        chapter_service = ChapterService(db)
        chapters_with_choices = await chapter_service.get_chapters_by_novel_with_user_choices(
            novel_id, current_user_id
        )

        return chapters_with_choices

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取章节列表失败: {str(e)}"
        )


@router.get("/chapters/{chapter_id}", response_model=ChapterResponse, summary="获取章节详情")
async def get_chapter_detail(
    chapter_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    获取特定章节的详细信息
    """
    try:
        chapter_service = ChapterService(db)

        # 获取包含用户选择的章节详情
        chapter_data = await chapter_service.get_chapter_by_id_with_user_choice(
            chapter_id, current_user_id
        )

        if not chapter_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="章节不存在"
            )

        # 验证用户权限
        novel_service = NovelService(db)
        novel = await novel_service.get_by_id(chapter_data["novel_id"])
        if not novel or novel.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此章节"
            )

        return chapter_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取章节详情失败: {str(e)}"
        )