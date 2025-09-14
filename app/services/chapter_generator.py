"""
章节生成服务
负责使用AI生成章节摘要、正文和选项
"""
import json

from typing import AsyncGenerator, Dict, Any

from fastapi import HTTPException

def json_dumps_chinese(obj):
    """JSON序列化时保持中文显示"""
    return json.dumps(obj, ensure_ascii=False)

from app.schemas.chapter import (
    ChapterSummary,
    ChapterFullContent,
    ChapterContext,
    StreamEvent
)
from app.schemas.novel import NovelGenre
from app.services.kimi import kimi_service
from app.services.chapter import ChapterService
from app.services.novel import NovelService


class ChapterGeneratorService:
    """章节生成服务类"""

    @staticmethod
    def _build_first_chapter_summary_prompt(
        world_setting: str,
        protagonist_info: str,
        genre: str
    ) -> tuple[str, str]:
        """构建第一章摘要生成的提示词"""

        if genre == "wuxia":
            system_prompt = """你是一位专业的武侠小说章节策划专家。
请根据给定的世界观和主角信息，为小说的第一章制定详细的剧情摘要。
第一章应该引人入胜，展现世界观，介绍主角，设置初始冲突。"""

            user_prompt = f"""请为武侠小说的第一章创建详细摘要。

世界观设定：
{world_setting}

主角信息：
{protagonist_info}

要求：
1. 创造一个吸引人的第一章标题
2. 设计引人入胜的开篇情节
3. 自然地展现世界观背景
4. 介绍主角的出场和基本特征
5. 设置推动剧情发展的初始冲突
6. 列出3-5个关键事件
7. 设计2-3个冲突点，为后续选择做铺垫"""

        else:  # scifi
            system_prompt = """你是一位专业的科幻小说章节策划专家。
请根据给定的世界观和主角信息，为小说的第一章制定详细的剧情摘要。
第一章应该展现未来世界的科技感，介绍主角，设置科幻元素的冲突。"""

            user_prompt = f"""请为科幻小说的第一章创建详细摘要。

世界观设定：
{world_setting}

主角信息：
{protagonist_info}

要求：
1. 创造一个有科幻感的第一章标题
2. 设计体现未来科技的开篇情节
3. 展现科幻世界观的独特元素
4. 介绍主角在科幻背景下的设定
5. 设置具有科幻特色的初始冲突
6. 列出3-5个关键事件
7. 设计2-3个冲突点，体现科幻主题"""

        return system_prompt, user_prompt

    @staticmethod
    def _build_next_chapter_summary_prompt(
        context: ChapterContext,
        genre: str
    ) -> tuple[str, str]:
        """构建后续章节摘要生成的提示词"""

        system_prompt = f"""你是一位专业的{"武侠" if genre == "wuxia" else "科幻"}小说章节策划专家。
请根据前续章节内容和用户的选择，为下一章制定合理的剧情摘要。
确保剧情逻辑连贯，选择的后果得到合理体现。"""

        # 构建前续章节信息
        recent_chapters_text = ""
        for chapter in context.recent_chapters[-3:]:  # 只用最近3章，避免prompt过长
            recent_chapters_text += f"""
第{chapter.chapter_number}章：{chapter.title}
摘要：{chapter.summary}
正文节选：{chapter.content[:500]}...
"""

        # 构建历史摘要
        history_text = ""
        if context.chapter_summaries:
            history_text = "更早章节摘要：\n"
            for summary in context.chapter_summaries[-5:]:  # 最多5个历史摘要
                history_text += f"第{summary['chapter_number']}章：{summary['title']} - {summary['summary']}\n"

        user_prompt = f"""请为下一章创建详细摘要。

世界观设定：
{context.world_setting}

主角信息：
{context.protagonist_info}

{history_text}

最近章节内容：
{recent_chapters_text}

用户选择的选项：
{context.selected_option}

要求：
1. 根据用户的选择，合理推进剧情发展
2. 保持与前续章节的逻辑连贯性
3. 创造符合选择后果的章节标题
4. 设计这一章的主要情节走向
5. 列出3-5个关键事件
6. 设计2-3个新的冲突点，为下一章的选择做准备"""

        return system_prompt, user_prompt

    @staticmethod
    def _build_chapter_content_prompt(
        summary: ChapterSummary,
        context: ChapterContext,
        genre: str
    ) -> tuple[str, str]:
        """构建章节正文和选项生成的提示词"""

        system_prompt = f"""你是一位专业的{"武侠" if genre == "wuxia" else "科幻"}小说作家。
请根据章节摘要和背景信息，创作出精彩的章节正文，并设计三个不同走向的选择选项。
正文应该生动有趣，选项应该提供明显不同的剧情发展方向。"""

        user_prompt = f"""请根据以下信息创作完整的章节内容。

章节摘要：
标题：{summary.title}
概要：{summary.summary}
关键事件：{', '.join(summary.key_events)}
冲突点：{', '.join(summary.conflicts)}

世界观背景：
{context.world_setting}

主角信息：
{context.protagonist_info}

要求：
1. 创作2000-3000字的精彩章节正文
2. 文笔生动，对话自然，情节紧凑
3. 体现摘要中的关键事件和冲突
4. 在章节结尾设计悬念，引出选择点
5. 创造三个选择选项，每个选项代表不同的发展方向：
   - 选项1：积极主动的选择
   - 选项2：谨慎保守的选择
   - 选项3：冒险或意外的选择
6. 每个选项都要有简短的影响提示

请用JSON格式返回，包含title、content、options字段。"""

        return system_prompt, user_prompt

    async def generate_first_chapter_stream(
        self,
        world_setting: str,
        protagonist_info: str,
        genre: str = "wuxia"
    ) -> AsyncGenerator[str, None]:
        """生成第一章的流式内容"""
        try:

            # Step 1: 生成第一章摘要
            yield f"event: status\ndata: {json_dumps_chinese({'message': '正在生成章节摘要...'})}\n\n"

            system_prompt, user_prompt = self._build_first_chapter_summary_prompt(
                world_setting,
                protagonist_info,
                genre
            )

            summary_result = await kimi_service.generate_structured_output(
                model_class=ChapterSummary,
                user_prompt=user_prompt,
                system_prompt=system_prompt
            )

            if not summary_result["success"]:
                error_msg = f"摘要生成失败: {summary_result.get('error', '未知错误')}"
                yield f"event: error\ndata: {json_dumps_chinese({'error': error_msg})}\n\n"
                return

            summary = ChapterSummary(**summary_result["data"])

            # 发送摘要事件
            yield f"event: summary\ndata: {json_dumps_chinese(summary.dict())}\n\n"

            # Step 2: 生成章节正文和选项
            yield f"event: status\ndata: {json_dumps_chinese({'message': '正在生成章节正文...'})}\n\n"

            context = ChapterContext(
                world_setting=world_setting,
                protagonist_info=protagonist_info,
                recent_chapters=[],
                chapter_summaries=[],
                selected_option=None
            )

            content_system_prompt, content_user_prompt = self._build_chapter_content_prompt(
                summary, context, genre
            )

            # 使用流式输出生成正文和选项
            async for stream_chunk in kimi_service.generate_streaming_output(
                model_class=ChapterFullContent,
                user_prompt=content_user_prompt,
                system_prompt=content_system_prompt
            ):
                # 将StreamChunk转换为SSE格式
                if stream_chunk.chunk_type == "content":
                    yield f"event: content\ndata: {json_dumps_chinese({'chunk': stream_chunk.data['chunk']})}\n\n"
                elif stream_chunk.chunk_type == "complete":
                    # 添加摘要信息到完成数据中
                    complete_data = stream_chunk.data['result']
                    complete_data['summary'] = summary.dict()
                    yield f"event: complete\ndata: {json_dumps_chinese(complete_data)}\n\n"
                elif stream_chunk.chunk_type == "error":
                    yield f"event: error\ndata: {json_dumps_chinese(stream_chunk.data)}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json_dumps_chinese({'error': f'生成过程异常: {str(e)}'})}\n\n"

    async def generate_next_chapter_stream(
        self,
        novel_id: int,
        selected_option_id: int,
        context: ChapterContext
    ) -> AsyncGenerator[str, None]:
        """生成后续章节的流式内容"""
        try:
            # Step 1: 生成章节摘要
            yield f"event: status\ndata: {json_dumps_chinese({'message': '正在生成章节摘要...'})}\n\n"

            system_prompt, user_prompt = self._build_next_chapter_summary_prompt(
                context, "wuxia"  # 需要从novel获取genre信息
            )

            summary_result = await kimi_service.generate_structured_output(
                model_class=ChapterSummary,
                user_prompt=user_prompt,
                system_prompt=system_prompt
            )

            if not summary_result["success"]:
                error_msg = f"摘要生成失败: {summary_result.get('error', '未知错误')}"
                yield f"event: error\ndata: {json_dumps_chinese({'error': error_msg})}\n\n"
                return

            summary = ChapterSummary(**summary_result["data"])

            # 发送摘要事件
            yield f"event: summary\ndata: {json_dumps_chinese(summary.dict())}\n\n"

            # Step 2: 生成章节正文和选项
            yield f"event: status\ndata: {json_dumps_chinese({'message': '正在生成章节正文...'})}\n\n"

            content_system_prompt, content_user_prompt = self._build_chapter_content_prompt(
                summary, context, "wuxia"
            )

            # 使用流式输出生成正文和选项
            async for stream_chunk in kimi_service.generate_streaming_output(
                model_class=ChapterFullContent,
                user_prompt=content_user_prompt,
                system_prompt=content_system_prompt
            ):
                # 将StreamChunk转换为SSE格式
                if stream_chunk.chunk_type == "content":
                    yield f"event: content\ndata: {json_dumps_chinese({'chunk': stream_chunk.data['chunk']})}\n\n"
                elif stream_chunk.chunk_type == "complete":
                    # 添加摘要信息到完成数据中
                    complete_data = stream_chunk.data['result']
                    complete_data['summary'] = summary.dict()
                    yield f"event: complete\ndata: {json_dumps_chinese(complete_data)}\n\n"
                elif stream_chunk.chunk_type == "error":
                    yield f"event: error\ndata: {json_dumps_chinese(stream_chunk.data)}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json_dumps_chinese({'error': f'生成过程异常: {str(e)}'})}\n\n"


# 全局章节生成服务实例
chapter_generator = ChapterGeneratorService()