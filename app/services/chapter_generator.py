"""
章节生成服务
负责使用AI生成章节摘要、正文和选项
"""
import json
import logging

from typing import AsyncGenerator, Dict, Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)

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
from app.services.stream_manager import StreamGenerationManager, managed_stream_generation
from app.utils.json_extractor import extract_content_from_json_fragment
from app.models.chapter import ChapterStatus


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
            system_prompt = """【重要约束】请务必使用标准简体中文输出，严禁使用繁体字。所有文字内容（包括标题、摘要、人名、地名、武功名称等）都必须符合现代简体中文书写规范。

你是一位专业的武侠小说章节策划专家。
请根据给定的世界观和主角信息，为小说的第一章制定详细的剧情摘要。
第一章应该引人入胜，展现世界观，介绍主角，设置初始冲突。"""

            user_prompt = f"""请为武侠小说的第一章创建详细摘要。

世界观设定：
{world_setting}

主角信息：
{protagonist_info}

要求：
1. 创造一个吸引人的第一章标题
2. 编写200-300字的详细摘要，概括本章剧情
3. 设计引人入胜的开篇情节
4. 自然地展现世界观背景
5. 介绍主角的出场和基本特征
6. 设置推动剧情发展的初始冲突
7. 列出3-5个关键事件
8. 设计2-3个冲突点，为后续选择做铺垫"""

        else:  # scifi
            system_prompt = """【重要约束】请务必使用标准简体中文输出，严禁使用繁体字。所有文字内容（包括标题、摘要、人名、地名、科技名称等）都必须符合现代简体中文书写规范。

你是一位专业的科幻小说章节策划专家。
请根据给定的世界观和主角信息，为小说的第一章制定详细的剧情摘要。
第一章应该展现未来世界的科技感，介绍主角，设置科幻元素的冲突。"""

            user_prompt = f"""请为科幻小说的第一章创建详细摘要。

世界观设定：
{world_setting}

主角信息：
{protagonist_info}

要求：
1. 创造一个有科幻感的第一章标题
2. 编写200-300字的详细摘要，概括本章剧情
3. 设计体现未来科技的开篇情节
4. 展现科幻世界观的独特元素
5. 介绍主角在科幻背景下的设定
6. 设置具有科幻特色的初始冲突
7. 列出3-5个关键事件
8. 设计2-3个冲突点，体现科幻主题"""

        return system_prompt, user_prompt

    @staticmethod
    def _build_next_chapter_summary_prompt(
        context: ChapterContext,
        genre: str
    ) -> tuple[str, str]:
        """构建后续章节摘要生成的提示词"""

        system_prompt = f"""【重要约束】请务必使用标准简体中文输出，严禁使用繁体字。所有文字内容（包括标题、摘要、人名、地名、武功名称等）都必须符合现代简体中文书写规范。

你是一位专业的{"武侠" if genre == "wuxia" else "科幻"}小说章节策划专家。
请根据前续章节内容和用户的选择，为下一章制定合理的剧情摘要。
确保剧情逻辑连贯，选择的后果得到合理体现。"""

        # 构建前续章节信息 - 最近5章提供完整内容
        recent_chapters_text = ""
        recent_chapter_numbers = set()
        for chapter in context.recent_chapters[-5:]:  # 最近5章完整内容
            # chapter 现在是字典格式，需要用字典的方式访问
            recent_chapter_numbers.add(chapter['chapter_number'])
            recent_chapters_text += f"""
第{chapter['chapter_number']}章：{chapter['title']}
摘要：{chapter['summary']}
正文：{chapter['content'] if chapter['content'] else ''}
"""

        # 构建历史摘要 - 排除最近5章，只要更早的章节摘要
        history_text = ""
        if context.chapter_summaries:
            # 过滤出不在最近5章中的历史章节
            earlier_summaries = [s for s in context.chapter_summaries
                               if s['chapter_number'] not in recent_chapter_numbers]
            if earlier_summaries:
                history_text = "更早章节摘要：\n"
                for summary in earlier_summaries:
                    history_text += f"第{summary['chapter_number']}章：{summary['title']} - {summary['summary']}\n"

        user_prompt = f"""请为下一章创建详细摘要。

世界观设定：
{context.world_setting}

主角信息：
{context.protagonist_info}

{history_text}

最近章节完整内容：
{recent_chapters_text}

用户选择的选项：
{context.selected_option}

要求：
1. 仔细分析用户的选择，合理推进剧情发展
2. 基于最近5章的完整内容，保持剧情逻辑连贯性
3. 确保选择的后果在新章节中得到充分体现
4. 创造符合选择后果的吸引人的章节标题
5. 编写200-300字的详细摘要，概括本章剧情发展
6. 设计这一章的主要情节走向和发展脉络
7. 列出3-5个关键事件，体现剧情推进
8. 设计2-3个新的冲突点，为下一章的选择做准备"""

        return system_prompt, user_prompt

    @staticmethod
    def _build_chapter_content_prompt(
        summary: ChapterSummary,
        context: ChapterContext,
        genre: str
    ) -> tuple[str, str]:
        """构建章节正文和选项生成的提示词"""

        system_prompt = f"""【重要约束】请务必使用标准简体中文输出，严禁使用繁体字。所有文字内容（包括标题、正文、对话、人名、地名、武功名称、选项文本等）都必须符合现代简体中文书写规范。

你是一位专业的{"武侠" if genre == "wuxia" else "科幻"}小说作家。
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
7. 为每个选项添加标签分析，包含以下五个维度（请严格使用指定的值，不要混淆）：
   - action_type: 行动倾向，必须是以下之一（active/conservative/risky/diplomatic/aggressive）
   - narrative_impact: 叙事影响，必须是以下之一（exploration/development/resolution/relationship/worldbuilding）
   - character_focus: 角色发展，必须是以下之一（self_growth/relationship/world_interaction/skill_development/moral_choice）
   - pacing_type: 节奏控制，必须是以下之一（slow/medium/fast）
   - emotional_tone: 情感色彩，必须是以下之一（positive/neutral/dark/humorous/mysterious）

【重要格式要求】：
- content字段只包含章节正文，以悬念或情境描写结尾
- **禁止在content中列举选项内容** (例如"一、...二、...三、...")
- **禁止在content中展示选项编号或选项文本**
- 选项内容全部放在options数组中，每个选项是一个独立对象
- content结尾应该是紧张的情境或悬念，让读者期待选择，但不要写出具体选择

错误示例：
content: "...他停住脚步。前路三岔：一、闯王府；二、上峨眉；三、入青城。他该如何选择？"

正确示例：
content: "...他停住脚步，三条山路在雨中若隐若现，每一条都通向未知的命运。"
options: [{{text: "直闯蜀王府...", ...}}, {{text: "先上峨眉医宗...", ...}}, ...]

请用JSON格式返回，包含content、options字段。
options数组中每个选项包含：text、impact_hint、tags字段。
tags字段包含上述五个标签维度。"""

        return system_prompt, user_prompt

    async def generate_first_chapter_stream(
        self,
        world_setting: str,
        protagonist_info: str,
        genre: str = "wuxia"
    ) -> AsyncGenerator[str, None]:
        """生成第一章的流式内容"""
        try:
            logger.info("🎯 开始生成第一章流式内容")
            logger.info(f"📚 类型: {genre}, 世界观长度: {len(world_setting)} 字符, 主角信息长度: {len(protagonist_info)} 字符")

            # Step 1: 生成第一章摘要
            logger.info("📝 Step 1: 开始生成章节摘要")
            yield f"event: status\ndata: {json_dumps_chinese({'message': '正在生成章节摘要...'})}\n\n"

            system_prompt, user_prompt = self._build_first_chapter_summary_prompt(
                world_setting,
                protagonist_info,
                genre
            )

            logger.info(f"🔧 构建摘要提示词完成, 系统提示词长度: {len(system_prompt)}, 用户提示词长度: {len(user_prompt)}")

            summary_result = await kimi_service.generate_structured_output(
                model_class=ChapterSummary,
                user_prompt=user_prompt,
                system_prompt=system_prompt
            )

            if not summary_result["success"]:
                error_msg = f"摘要生成失败: {summary_result.get('error', '未知错误')}"
                logger.error(f"❌ 章节摘要生成失败: {error_msg}")
                yield f"event: error\ndata: {json_dumps_chinese({'error': error_msg})}\n\n"
                return

            summary = ChapterSummary(**summary_result["data"])
            logger.info(f"✅ Step 1 完成: 章节摘要生成成功")
            logger.info(f"📖 章节标题: {summary.title}")
            logger.info(f"🎭 关键冲突: {', '.join(summary.conflicts)}")
            logger.info(f"📋 关键事件数: {len(summary.key_events)}")

            # 发送摘要事件
            yield f"event: summary\ndata: {json_dumps_chinese(summary.dict())}\n\n"

            # Step 2: 生成章节正文和选项
            logger.info("✍️  Step 2: 开始生成章节正文和选项")
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

            logger.info(f"🔧 构建正文提示词完成, 系统提示词长度: {len(content_system_prompt)}, 用户提示词长度: {len(content_user_prompt)}")

            # 使用流式输出生成正文和选项
            content_char_count = 0

            async for stream_chunk in kimi_service.generate_streaming_output(
                model_class=ChapterFullContent,
                user_prompt=content_user_prompt,
                system_prompt=content_system_prompt
            ):
                # 将StreamChunk转换为SSE格式
                if stream_chunk.chunk_type == "content":
                    # 原始chunk（JSON片段）
                    chunk_text = stream_chunk.data['chunk']

                    # 直接发送原始chunk（待重新设计解析逻辑）
                    if chunk_text:
                        content_char_count += len(chunk_text)
                        yield f"event: content\ndata: {json_dumps_chinese({'text': chunk_text})}\n\n"
                elif stream_chunk.chunk_type == "complete":
                    logger.info(f"✅ Step 2 完成: 章节正文和选项生成成功")
                    # 组装完整数据
                    complete_data = stream_chunk.data['result']
                    complete_data['title'] = summary.title  # 使用摘要阶段的title
                    complete_data['summary'] = summary.dict()

                    # 统计信息
                    content_length = len(complete_data.get('content', ''))
                    options_count = len(complete_data.get('options', []))
                    logger.info(f"📊 正文字符数: {content_length}, 选项数量: {options_count}")

                    yield f"event: complete\ndata: {json_dumps_chinese(complete_data)}\n\n"
                elif stream_chunk.chunk_type == "error":
                    logger.error(f"❌ 正文生成过程中出错: {stream_chunk.data}")
                    yield f"event: error\ndata: {json_dumps_chinese(stream_chunk.data)}\n\n"

        except Exception as e:
            logger.error(f"❌ 第一章生成过程异常: {str(e)}", exc_info=True)
            yield f"event: error\ndata: {json_dumps_chinese({'error': f'生成过程异常: {str(e)}'})}\n\n"

    async def generate_next_chapter_stream(
        self,
        novel_id: int,
        selected_option_id: int,
        context: ChapterContext
    ) -> AsyncGenerator[str, None]:
        """生成后续章节的流式内容"""
        try:
            logger.info(f"🎯 开始生成后续章节流式内容")
            logger.info(f"📚 小说ID: {novel_id}, 选择的选项ID: {selected_option_id}")
            logger.info(f"📝 已有章节数: {len(context.recent_chapters)}, 历史摘要数: {len(context.chapter_summaries)}")

            # Step 1: 获取章节上下文
            logger.info("📋 Step 0: 获取章节上下文完成")
            if context.selected_option:
                logger.info(f"🎯 用户选择: {context.selected_option}")

            # Step 2: 生成章节摘要
            logger.info("📝 Step 1: 开始生成章节摘要")
            yield f"event: status\ndata: {json_dumps_chinese({'message': '正在生成章节摘要...'})}\n\n"

            system_prompt, user_prompt = self._build_next_chapter_summary_prompt(
                context, "wuxia"  # 需要从novel获取genre信息
            )

            logger.info(f"🔧 构建摘要提示词完成, 系统提示词长度: {len(system_prompt)}, 用户提示词长度: {len(user_prompt)}")

            summary_result = await kimi_service.generate_structured_output(
                model_class=ChapterSummary,
                user_prompt=user_prompt,
                system_prompt=system_prompt
            )

            if not summary_result["success"]:
                error_msg = f"摘要生成失败: {summary_result.get('error', '未知错误')}"
                logger.error(f"❌ 后续章节摘要生成失败: {error_msg}")
                yield f"event: error\ndata: {json_dumps_chinese({'error': error_msg})}\n\n"
                return

            summary = ChapterSummary(**summary_result["data"])
            logger.info(f"✅ Step 1 完成: 后续章节摘要生成成功")
            logger.info(f"📖 章节标题: {summary.title}")
            logger.info(f"🎭 关键冲突: {', '.join(summary.conflicts)}")
            logger.info(f"📋 关键事件数: {len(summary.key_events)}")

            # 发送摘要事件
            yield f"event: summary\ndata: {json_dumps_chinese(summary.dict())}\n\n"

            # Step 3: 生成章节正文和选项
            logger.info("✍️  Step 2: 开始生成章节正文和选项")
            yield f"event: status\ndata: {json_dumps_chinese({'message': '正在生成章节正文...'})}\n\n"

            content_system_prompt, content_user_prompt = self._build_chapter_content_prompt(
                summary, context, "wuxia"
            )

            logger.info(f"🔧 构建正文提示词完成, 系统提示词长度: {len(content_system_prompt)}, 用户提示词长度: {len(content_user_prompt)}")

            # 使用流式输出生成正文和选项
            async for stream_chunk in kimi_service.generate_streaming_output(
                model_class=ChapterFullContent,
                user_prompt=content_user_prompt,
                system_prompt=content_system_prompt
            ):
                # 将StreamChunk转换为SSE格式
                if stream_chunk.chunk_type == "content":
                    # 原始chunk（JSON片段）
                    chunk_text = stream_chunk.data['chunk']

                    # 直接发送原始chunk（待重新设计解析逻辑）
                    if chunk_text:
                        yield f"event: content\ndata: {json_dumps_chinese({'text': chunk_text})}\n\n"
                elif stream_chunk.chunk_type == "complete":
                    logger.info(f"✅ Step 2 完成: 后续章节正文和选项生成成功")
                    # 组装完整数据
                    complete_data = stream_chunk.data['result']
                    complete_data['title'] = summary.title  # 使用摘要阶段的title
                    complete_data['summary'] = summary.dict()

                    # 统计信息
                    content_length = len(complete_data.get('content', ''))
                    options_count = len(complete_data.get('options', []))
                    logger.info(f"📊 正文字符数: {content_length}, 选项数量: {options_count}")

                    yield f"event: complete\ndata: {json_dumps_chinese(complete_data)}\n\n"
                elif stream_chunk.chunk_type == "error":
                    logger.error(f"❌ 后续章节正文生成过程中出错: {stream_chunk.data}")
                    yield f"event: error\ndata: {json_dumps_chinese(stream_chunk.data)}\n\n"

        except Exception as e:
            logger.error(f"❌ 后续章节生成过程异常: {str(e)}", exc_info=True)
            yield f"event: error\ndata: {json_dumps_chinese({'error': f'生成过程异常: {str(e)}'})}\n\n"

    async def generate_first_chapter_background(
        self,
        chapter_id: int,
        novel_id: int,
        world_setting: str,
        protagonist_info: str,
        genre: str
    ) -> None:
        """
        后台任务：生成第一章（存入Redis）

        流程：
        1. 生成摘要
        2. 生成正文（流式）→ 提取content → 存Redis
        3. 完成后存PostgreSQL

        注意: 后台任务创建自己的数据库session,避免session被提前关闭
        """
        from app.db.database import async_session_maker

        session_id = StreamGenerationManager.generate_session_id()

        # 后台任务创建自己的数据库session
        async with async_session_maker() as db:
            async with managed_stream_generation(chapter_id, novel_id, session_id, db) as manager:
                try:
                    logger.info(f"🎯 后台任务：开始生成第一章 {chapter_id}")

                    # Step 1: 生成摘要
                    system_prompt, user_prompt = self._build_first_chapter_summary_prompt(
                        world_setting, protagonist_info, genre
                    )

                    summary_result = await kimi_service.generate_structured_output(
                        model_class=ChapterSummary,
                        user_prompt=user_prompt,
                        system_prompt=system_prompt
                    )

                    if not summary_result["success"]:
                        raise Exception(f"摘要生成失败: {summary_result.get('error')}")

                    summary = ChapterSummary(**summary_result["data"])
                    logger.info(f"✅ 摘要生成成功: {summary.title}")

                    # 初始化Redis（设置title）
                    await manager.start_generation(summary.title)

                    # Step 2: 生成正文
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

                    # 累积JSON用于提取
                    accumulated_json = ""
                    previous_content = ""  # 追踪上一次的内容,用于计算增量

                    async for stream_chunk in kimi_service.generate_streaming_output(
                        model_class=ChapterFullContent,
                        user_prompt=content_user_prompt,
                        system_prompt=content_system_prompt
                    ):
                        if stream_chunk.chunk_type == "content":
                            # 累积JSON片段
                            accumulated_json = stream_chunk.data['accumulated']

                            # 提取纯文本content(这是累积的全部内容)
                            current_content = extract_content_from_json_fragment(accumulated_json)

                            # 计算增量chunk
                            if current_content and len(current_content) > len(previous_content):
                                incremental_chunk = current_content[len(previous_content):]
                                await manager.append_chunk(incremental_chunk)
                                previous_content = current_content

                        elif stream_chunk.chunk_type == "complete":
                            # 生成完成
                            result = stream_chunk.data['result']
                            final_content = result.get('content', '')
                            options = result.get('options', [])

                            logger.info(f"✅ 正文生成完成: {len(final_content)} 字符, {len(options)} 个选项")

                            # 最终写入PostgreSQL并清理Redis(包含summary)
                            await manager.complete_generation(
                                final_content,
                                options,
                                summary=summary.summary  # 传入摘要文本
                            )

                        elif stream_chunk.chunk_type == "error":
                            raise Exception(f"生成错误: {stream_chunk.data}")

                    logger.info(f"🎉 第一章生成完成: {chapter_id}")

                except Exception as e:
                    logger.error(f"❌ 第一章后台生成失败: {e}")
                    raise

    async def generate_next_chapter_background(
        self,
        chapter_id: int,
        novel_id: int,
        selected_option_id: int,
        genre: str
    ) -> None:
        """
        后台任务：生成后续章节（存入Redis）

        注意: 后台任务创建自己的数据库session,避免session被提前关闭
        """
        from app.db.database import async_session_maker

        session_id = StreamGenerationManager.generate_session_id()

        # 后台任务创建自己的数据库session
        async with async_session_maker() as db:
            async with managed_stream_generation(chapter_id, novel_id, session_id, db) as manager:
                try:
                    logger.info(f"🎯 后台任务：开始生成后续章节 {chapter_id}")

                    # 构建上下文（省略详细代码，与generate_next_chapter_stream类似）
                    chapter_service = ChapterService(db)
                    novel_service = NovelService(db)

                    # 获取小说信息和章节历史
                    novel = await novel_service.get_by_id(novel_id)
                    chapters = await chapter_service.get_chapters_by_novel(novel_id)

                    # 构建上下文
                    recent_chapters = [
                        {
                            "chapter_number": ch.chapter_number,
                            "title": ch.title,
                            "summary": getattr(ch, 'summary', ''),
                            "content": ch.content[:500] if ch.content else ''
                        }
                        for ch in chapters[-3:] if ch.status == ChapterStatus.COMPLETED
                    ]

                    context = ChapterContext(
                        world_setting=novel.background_setting or "",
                        protagonist_info=novel.character_setting or "",
                        recent_chapters=recent_chapters,
                        chapter_summaries=[],
                        selected_option=None  # TODO: 获取选项信息
                    )

                    # Step 1: 生成摘要
                    system_prompt, user_prompt = self._build_next_chapter_summary_prompt(context, genre)

                    summary_result = await kimi_service.generate_structured_output(
                        model_class=ChapterSummary,
                        user_prompt=user_prompt,
                        system_prompt=system_prompt
                    )

                    if not summary_result["success"]:
                        raise Exception(f"摘要生成失败: {summary_result.get('error')}")

                    summary = ChapterSummary(**summary_result["data"])
                    logger.info(f"✅ 摘要生成成功: {summary.title}")

                    await manager.start_generation(summary.title)

                    # Step 2: 生成正文
                    content_system_prompt, content_user_prompt = self._build_chapter_content_prompt(
                        summary, context, genre
                    )

                    accumulated_json = ""
                    previous_content = ""  # 追踪上一次的内容,用于计算增量

                    async for stream_chunk in kimi_service.generate_streaming_output(
                        model_class=ChapterFullContent,
                        user_prompt=content_user_prompt,
                        system_prompt=content_system_prompt
                    ):
                        if stream_chunk.chunk_type == "content":
                            accumulated_json = stream_chunk.data['accumulated']
                            current_content = extract_content_from_json_fragment(accumulated_json)

                            # 计算增量chunk
                            if current_content and len(current_content) > len(previous_content):
                                incremental_chunk = current_content[len(previous_content):]
                                await manager.append_chunk(incremental_chunk)
                                previous_content = current_content

                        elif stream_chunk.chunk_type == "complete":
                            result = stream_chunk.data['result']
                            final_content = result.get('content', '')
                            options = result.get('options', [])

                            # 最终写入PostgreSQL并清理Redis(包含summary)
                            await manager.complete_generation(
                                final_content,
                                options,
                                summary=summary.summary  # 传入摘要文本
                            )

                        elif stream_chunk.chunk_type == "error":
                            raise Exception(f"生成错误: {stream_chunk.data}")

                    logger.info(f"🎉 后续章节生成完成: {chapter_id}")

                except Exception as e:
                    logger.error(f"❌ 后续章节后台生成失败: {e}")
                    raise


# 全局章节生成服务实例
chapter_generator = ChapterGeneratorService()