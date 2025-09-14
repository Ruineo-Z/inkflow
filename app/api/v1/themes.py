from fastapi import APIRouter
from app.schemas.novel import NovelGenre

router = APIRouter()

@router.get("", summary="获取可用的小说主题")
async def get_available_themes():
    """
    获取系统支持的小说主题列表

    RESTful: GET /themes
    """
    return {
        "themes": [
            {
                "id": NovelGenre.WUXIA.value,
                "name": "武侠",
                "description": "以武功、江湖为背景的传统中国文学题材",
                "features": [
                    "包含朝代背景设定",
                    "完整的武功修炼体系",
                    "丰富的武林门派设定",
                    "江湖恩怨情仇主线"
                ]
            },
            {
                "id": NovelGenre.SCIFI.value,
                "name": "科幻",
                "description": "以未来科技、太空探索为背景的文学题材",
                "features": [
                    "未来科技水平设定",
                    "太空文明发展状况",
                    "AI技术发展程度",
                    "外星种族与势力"
                ]
            }
        ]
    }