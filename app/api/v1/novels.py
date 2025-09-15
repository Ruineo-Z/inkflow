from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.database import get_db
from app.services.novel_generator import novel_generator
from app.services.novel import NovelService
from app.schemas.novel import (
    NovelGenre,
    NovelCreate,
    NovelResponse,
    NovelDetail
)
from app.core.security import get_current_user_id
from pydantic import BaseModel, Field

# 创建小说请求模型
class CreateNovelRequest(BaseModel):
    genre: NovelGenre = Field(description="小说类型（武侠或科幻）")
    additional_requirements: Optional[str] = Field(default="", description="额外要求和偏好")

router = APIRouter()

@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, summary="创建小说")
async def create_novel(
    request: CreateNovelRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    创建小说 - 用户选择主题，AI自动生成标题、世界观、主角信息等完整内容

    RESTful: POST /novels
    """
    try:
        # 1. 使用AI生成完整的小说初始设定
        generation_result = await novel_generator.generate_complete_novel(
            genre=request.genre,
            requirements=request.additional_requirements
        )

        if not generation_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"生成小说内容失败: {generation_result.get('error', '未知错误')}"
            )

        # 2. 解析生成的数据
        novel_data = generation_result.get("data", {})
        world_setting = novel_data.get("world_setting", {})
        protagonist = novel_data.get("protagonist", {})

        # 将生成的数据转换为字符串格式存储
        world_setting_str = f"背景：{world_setting.get('background', '')}"
        if request.genre == NovelGenre.WUXIA:
            world_setting_str += f"\n朝代：{world_setting.get('dynasty', '')}"
            world_setting_str += f"\n武功体系：{world_setting.get('martial_arts_system', '')}"
            world_setting_str += f"\n主要门派：{', '.join(world_setting.get('major_sects', []))}"
        else:  # SCIFI
            world_setting_str += f"\n科技水平：{world_setting.get('technology_level', '')}"
            world_setting_str += f"\n太空设定：{world_setting.get('space_setting', '')}"
            world_setting_str += f"\n外星种族：{', '.join(world_setting.get('alien_races', []))}"

        protagonist_str = f"姓名：{protagonist.get('name', '')}"
        protagonist_str += f"\n性格：{protagonist.get('personality', '')}"
        protagonist_str += f"\n背景：{protagonist.get('background', '')}"
        protagonist_str += f"\n动机：{protagonist.get('motivation', '')}"

        # 3. 创建小说记录
        novel_create = NovelCreate(
            title=novel_data.get("title", "未命名小说"),
            world_setting=world_setting_str,
            protagonist_info=protagonist_str,
            user_id=current_user_id
        )

        novel_service = NovelService(db)
        novel = await novel_service.create(novel_create)

        return {
            "message": "小说创建成功",
            "novel_id": novel.id,
            "generated_content": {
                "title": novel_data.get("title"),
                "summary": novel_data.get("summary"),
                "world_setting": world_setting,
                "protagonist": protagonist,
                "genre": request.genre.value
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建小说时发生错误: {str(e)}"
        )

@router.get("/{novel_id}", response_model=NovelDetail, summary="获取小说详情")
async def get_novel(
    novel_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    获取小说详情

    RESTful: GET /novels/{id}
    """
    try:
        novel_service = NovelService(db)
        novel = await novel_service.get_by_id(novel_id)

        if not novel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="小说不存在"
            )

        # 验证权限
        if novel.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此小说"
            )

        return novel

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取小说详情时发生错误: {str(e)}"
        )

@router.get("", response_model=list[NovelResponse], summary="获取用户的小说列表")
async def get_user_novels(
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户的所有小说

    RESTful: GET /novels
    """
    try:
        novel_service = NovelService(db)
        novels = await novel_service.get_by_user_id(current_user_id)
        return novels

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取小说列表时发生错误: {str(e)}"
        )


@router.delete("/{novel_id}", summary="删除小说（级联删除）")
async def delete_novel(
    novel_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    删除小说及其所有相关数据（级联删除）

    将删除：
    - 小说本身
    - 所有章节
    - 所有选项
    - 所有用户选择记录

    RESTful: DELETE /novels/{id}
    """
    try:
        novel_service = NovelService(db)

        # 1. 检查小说是否存在
        novel = await novel_service.get_by_id(novel_id)
        if not novel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="小说不存在"
            )

        # 2. 验证权限：只能删除自己的小说
        if novel.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此小说"
            )

        # 3. 执行级联删除
        success = await novel_service.delete(novel_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除小说失败"
            )

        return {
            "message": "小说删除成功",
            "novel_id": novel_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除小说时发生错误: {str(e)}"
        )