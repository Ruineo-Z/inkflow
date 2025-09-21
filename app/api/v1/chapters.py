import json
import logging
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

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
    """
    try:
        logger.info(f"🚀 开始章节生成请求 - 小说ID: {novel_id}, 用户ID: {current_user_id}")
        
        chapter_service = ChapterService(db)
        novel_service = NovelService(db)

        # 验证小说存在且属于当前用户
        logger.info(f"📚 验证小说权限 - 小说ID: {novel_id}")
        novel = await novel_service.get_by_id(novel_id)
        logger.info(f"📖 小说查询结果: {novel.title if novel else 'None'}")
        
        if not novel:
            logger.error(f"❌ 小说不存在 - ID: {novel_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="小说不存在"
            )
        
        if novel.user_id != current_user_id:
            logger.error(f"❌ 用户无权限 - 小说用户ID: {novel.user_id}, 当前用户ID: {current_user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此小说"
            )

        chapter_service = ChapterService(db)
        latest_chapter_number = await chapter_service.get_latest_chapter_number(novel_id)
        logger.info(f"📊 最新章节号: {latest_chapter_number}, 是否第一章: {latest_chapter_number == 0}")
        
        if latest_chapter_number == 0:
            # 第一章生成
            logger.info(f"✨ 开始生成第一章 - 小说: {novel.title}")

            async def first_chapter_stream():
                chapter_id = None
                try:
                    logger.info(f"🎭 第一章生成参数 - 背景: {novel.background_setting[:50] if novel.background_setting else 'None'}...")
                    logger.info(f"👤 主角设定: {novel.character_setting[:50] if novel.character_setting else 'None'}...")
                    logger.info(f"🎨 主题: {novel.theme or 'wuxia'}")
                    
                    async for event_data in chapter_generator.generate_first_chapter_stream(
                        world_setting=novel.background_setting or "",
                        protagonist_info=novel.character_setting or "",
                        genre=novel.theme or "wuxia"  # 使用novel中的实际theme
                    ):
                        # 解析事件数据
                        if event_data.startswith("event: summary"):
                            # 提取摘要数据并创建章节记录
                            data_line = event_data.split('\n')[1]  # data: {...}
                            summary_data = json.loads(data_line.split('data: ')[1])
                            
                            from app.schemas.chapter import ChapterSummary
                            summary = ChapterSummary(**summary_data)
                            chapter = await chapter_service.create_chapter_with_summary(
                                novel_id=novel_id,
                                chapter_number=1,
                                summary_data=summary
                            )
                            chapter_id = chapter.id
                            
                        elif event_data.startswith("event: complete") and chapter_id:
                            # 提取完整数据并保存内容和选项
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
                    logger.error(f"❌ 第一章生成异常: {str(e)}")
                    logger.exception("第一章生成详细异常信息:")
                    yield f"event: error\ndata: {json.dumps({'error': f'生成失败: {str(e)}'}, ensure_ascii=False)}\n\n"

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
            logger.info(f"📚 开始生成后续章节 - 小说: {novel.title}, 现有章节数: {latest_chapter_number}")

            # 预先获取必要数据，避免在流式响应中进行复杂数据库操作
            try:
                # 获取用户最新选择
                logger.info(f"🎯 获取用户最新选择 - 用户ID: {current_user_id}, 小说ID: {novel_id}")
                selected_option_id = await chapter_service.get_latest_user_choice(
                    user_id=current_user_id,
                    novel_id=novel_id
                )

                if not selected_option_id:
                    logger.error(f"❌ 未找到用户选择 - 用户ID: {current_user_id}, 小说ID: {novel_id}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="未找到用户选择，请先选择一个选项"
                    )

                logger.info(f"🎯 选择的选项ID: {selected_option_id}")

                # 获取生成上下文
                logger.info(f"📋 构建章节生成上下文")
                context = await chapter_service.get_generation_context(
                    novel_id, selected_option_id
                )
                logger.info(f"📊 上下文构建完成 - 最近章节数: {len(context.recent_chapters)}, 历史摘要数: {len(context.chapter_summaries)}")

                # 获取下一章节号
                next_chapter_num = await chapter_service.get_latest_chapter_number(novel_id) + 1
                logger.info(f"📖 下一章节号: {next_chapter_num}")

            except Exception as e:
                logger.error(f"❌ 预处理数据时出错: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"准备生成数据失败: {str(e)}"
                )

            async def next_chapter_stream():
                chapter_id = None
                try:
                    logger.info(f"🚀 开始流式生成后续章节")
                    
                    async for event_data in chapter_generator.generate_next_chapter_stream(
                        novel_id, selected_option_id, context
                    ):
                        try:
                            # 处理摘要事件 - 创建章节记录
                            if event_data.startswith("event: summary"):
                                data_line = event_data.split('\n')[1]
                                summary_data = json.loads(data_line.split('data: ')[1])

                                from app.schemas.chapter import ChapterSummary
                                summary = ChapterSummary(**summary_data)
                                
                                # 使用新的数据库会话进行章节创建
                                from app.db.database import async_session_maker
                                async with async_session_maker() as new_db:
                                    new_chapter_service = ChapterService(new_db)
                                    chapter = await new_chapter_service.create_chapter_with_summary(
                                        novel_id=novel_id,
                                        chapter_number=next_chapter_num,
                                        summary_data=summary
                                    )
                                    chapter_id = chapter.id
                                    await new_db.commit()
                                    logger.info(f"✅ 章节创建成功 - ID: {chapter_id}")

                            # 处理完成事件 - 保存内容和选项
                            elif event_data.startswith("event: complete") and chapter_id:
                                data_line = event_data.split('\n')[1]
                                complete_data = json.loads(data_line.split('data: ')[1])

                                # 使用新的数据库会话进行内容更新
                                from app.db.database import async_session_maker
                                async with async_session_maker() as new_db:
                                    new_chapter_service = ChapterService(new_db)
                                    await new_chapter_service.update_chapter_content(
                                        chapter_id, complete_data["content"]
                                    )
                                    await new_chapter_service.create_chapter_options(
                                        chapter_id, complete_data["options"]
                                    )
                                    await new_db.commit()
                                    logger.info(f"✅ 章节内容和选项保存成功")

                                complete_data["chapter_id"] = chapter_id
                                yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
                                continue

                            yield event_data
                            
                        except Exception as inner_e:
                            logger.error(f"❌ 处理流式事件时出错: {str(inner_e)}")
                            error_msg = f"event: error\ndata: {json.dumps({'error': f'处理事件失败: {str(inner_e)}'})}"
                            yield f"{error_msg}\n\n"
                            break

                except Exception as e:
                    logger.error(f"❌ 章节生成流程出错: {str(e)}")
                    logger.exception("章节生成详细异常信息:")
                    yield f"event: error\ndata: {json.dumps({'error': f'生成失败: {str(e)}'}, ensure_ascii=False)}\n\n"

            return StreamingResponse(
                next_chapter_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                }
            )

    except HTTPException as he:
        logger.error(f"❌ HTTP异常: {he.detail}")
        raise
    except Exception as e:
        logger.error(f"❌ 章节生成API异常: {str(e)}")
        logger.exception("章节生成API详细异常信息:")
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
    获取章节详情，包含用户选择信息
    """
    try:
        chapter_service = ChapterService(db)
        
        # 获取章节详情（包含用户选择）
        chapter_with_choice = await chapter_service.get_chapter_with_user_choice(
            chapter_id, current_user_id
        )
        
        if not chapter_with_choice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="章节不存在"
            )
        
        # 验证用户权限（通过小说验证）
        novel_service = NovelService(db)
        novel = await novel_service.get_by_id(chapter_with_choice.novel_id)
        if not novel or novel.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此章节"
            )
        
        return chapter_with_choice
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取章节详情失败: {str(e)}"
        )