from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.db.database import get_db
from app.core.security import get_current_user_id
from app.services.chapter import ChapterService
from app.services.chapter_generator import chapter_generator
from app.services.novel import NovelService
from app.schemas.chapter import (
    GenerateChapterRequest,
    SaveUserChoiceRequest,
    ChapterResponse,
    UserChoiceResponse
)

router = APIRouter()


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
        if request.selected_option_id is None:
            # 第一章生成

            # 检查是否已经有章节（防止重复生成第一章）
            latest_chapter_num = await chapter_service.get_latest_chapter_number(novel_id)
            if latest_chapter_num > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="第一章已存在，请使用选项生成后续章节"
                )

            async def first_chapter_stream():
                chapter_id = None
                try:
                    async for event_data in chapter_generator.generate_first_chapter_stream(
                        world_setting=novel.world_setting or "",
                        protagonist_info=novel.protagonist_info or "",
                        genre="wuxia"  # 需要从novel获取实际的genre
                    ):
                        # 解析事件数据
                        if event_data.startswith("event: summary"):
                            # 提取摘要数据并创建章节记录
                            data_line = event_data.split('\n')[1]  # data: {...}
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

                        elif event_data.startswith("event: complete") and chapter_id:
                            # 提取完整数据并保存到数据库
                            data_line = event_data.split('\n')[1]
                            complete_data = json.loads(data_line.split('data: ')[1])

                            # 更新章节内容
                            await chapter_service.update_chapter_content(
                                chapter_id, complete_data["content"]
                            )

                            # 创建选项
                            await chapter_service.create_chapter_options(
                                chapter_id, complete_data["options"]
                            )

                            # 添加章节ID到返回数据
                            complete_data["chapter_id"] = chapter_id
                            yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
                            continue

                        yield event_data

                except Exception as e:
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

            # 验证选项存在
            # TODO: 验证option_id的有效性

            async def next_chapter_stream():
                try:
                    # 获取生成上下文
                    context = await chapter_service.get_generation_context(
                        novel_id, request.selected_option_id
                    )

                    # 获取下一章节号
                    next_chapter_num = await chapter_service.get_latest_chapter_number(novel_id) + 1

                    chapter_id = None

                    async for event_data in chapter_generator.generate_next_chapter_stream(
                        novel_id, request.selected_option_id, context
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

                        elif event_data.startswith("event: complete") and chapter_id:
                            data_line = event_data.split('\n')[1]
                            complete_data = json.loads(data_line.split('data: ')[1])

                            # 保存内容和选项
                            await chapter_service.update_chapter_content(
                                chapter_id, complete_data["content"]
                            )
                            await chapter_service.create_chapter_options(
                                chapter_id, complete_data["options"]
                            )

                            complete_data["chapter_id"] = chapter_id
                            yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
                            continue

                        yield event_data

                except Exception as e:
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

        # 获取章节列表
        chapter_service = ChapterService(db)
        chapters = await chapter_service.get_chapters_by_novel(novel_id)

        return [ChapterResponse.from_orm(chapter) for chapter in chapters]

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
        chapter = await chapter_service.get_chapter_by_id(chapter_id)

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="章节不存在"
            )

        # 验证用户权限
        novel_service = NovelService(db)
        novel = await novel_service.get_by_id(chapter.novel_id)
        if not novel or novel.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此章节"
            )

        return ChapterResponse.from_orm(chapter)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取章节详情失败: {str(e)}"
        )