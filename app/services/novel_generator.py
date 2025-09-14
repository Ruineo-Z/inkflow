"""
小说生成服务
负责根据主题生成世界观和主角信息
"""
from typing import Dict, Any, Tuple
from pydantic import BaseModel

from app.schemas.novel import NovelGenre, WuxiaWorldSetting, SciFiWorldSetting, ProtagonistProfile, NovelFullProfile
from app.services.kimi import kimi_service


class NovelGeneratorService:
    """小说生成服务类"""

    @staticmethod
    def _get_world_setting_prompts(genre: NovelGenre) -> Tuple[str, str, type[BaseModel]]:
        """
        根据小说类型获取世界观生成的提示词和模型类

        Args:
            genre: 小说类型

        Returns:
            (system_prompt, user_prompt_template, model_class)
        """
        if genre == NovelGenre.WUXIA:
            system_prompt = """你是一位专业的武侠小说世界观设定专家。
请根据用户的要求，创造一个丰富详细的武侠世界观。
注意要包含具体的朝代背景、完整的武功体系、主要门派等关键元素。
你的设定要有深度和可信度，能够支撑一个完整的武侠故事。"""

            user_prompt_template = """请为我创建一个武侠小说的世界观设定。

要求：
1. 选择一个具体的历史朝代作为背景（可以是真实或架空）
2. 设计一个完整的武功修炼体系
3. 创造3-5个有特色的武林门派
4. 整个世界观要有内在逻辑和一致性

{additional_requirements}"""

            return system_prompt, user_prompt_template, WuxiaWorldSetting

        else:  # SCIFI
            system_prompt = """你是一位专业的科幻小说世界观设定专家。
请根据用户的要求，创造一个引人入胜的科幻世界观。
注意要包含合理的科技设定、太空背景、外星文明等科幻元素。
你的设定要有科学基础和想象力，能够支撑一个完整的科幻故事。"""

            user_prompt_template = """请为我创建一个科幻小说的世界观设定。

要求：
1. 设定一个未来的时间背景和科技水平
2. 描述太空文明的发展状况
3. 设计AI技术的发展程度和影响
4. 创造1-3个外星种族或势力
5. 整个世界观要有科学逻辑性

{additional_requirements}"""

            return system_prompt, user_prompt_template, SciFiWorldSetting

    @staticmethod
    def _get_protagonist_prompts(genre: NovelGenre) -> Tuple[str, str]:
        """
        根据小说类型获取主角生成的提示词

        Args:
            genre: 小说类型

        Returns:
            (system_prompt, user_prompt_template)
        """
        if genre == NovelGenre.WUXIA:
            system_prompt = """你是一位专业的武侠小说角色设定专家。
请根据用户要求和世界观背景，创造一个有血有肉的武侠主角。
角色要有鲜明的性格特点、合理的背景故事和明确的动机目标。"""

            user_prompt_template = """请为武侠小说创建一个主角角色。

世界观背景：
{world_background}

要求：
1. 角色要符合武侠世界的设定
2. 要有引人入胜的背景故事
3. 性格特点要鲜明但不极端
4. 动机要与世界观相符
5. 要有成长空间和发展潜力

{additional_requirements}"""

        else:  # SCIFI
            system_prompt = """你是一位专业的科幻小说角色设定专家。
请根据用户要求和世界观背景，创造一个适合科幻世界的主角。
角色要有适应未来世界的特质、合理的科技背景和明确的使命感。"""

            user_prompt_template = """请为科幻小说创建一个主角角色。

世界观背景：
{world_background}

要求：
1. 角色要符合科幻世界的设定
2. 要有与科技时代相关的背景
3. 性格要适应未来社会环境
4. 动机要与科幻主题相符
5. 要有面对未知挑战的能力

{additional_requirements}"""

        return system_prompt, user_prompt_template

    @staticmethod
    def _get_complete_novel_prompts(genre: NovelGenre) -> Tuple[str, str]:
        """
        根据小说类型获取完整小说生成的提示词

        Args:
            genre: 小说类型

        Returns:
            (system_prompt, user_prompt_template)
        """
        if genre == NovelGenre.WUXIA:
            system_prompt = """你是一位专业的武侠小说策划专家。
请根据用户要求，创造一个完整的武侠小说初始设定，包括吸引人的标题、世界观、主角设定。
要求设定有深度、逻辑性强，能够支撑一个精彩的武侠故事。"""

            user_prompt_template = """请为我创建一个完整的武侠小说初始设定。

要求包含：
1. 一个吸引人的小说标题
2. 简洁有力的小说简介（2-3句话）
3. 完整的武侠世界观设定（朝代、武功体系、门派等）
4. 主角的详细信息（姓名、性格、背景、动机等）

整体风格要统一，各部分要相互呼应。

{additional_requirements}"""

        else:  # SCIFI
            system_prompt = """你是一位专业的科幻小说策划专家。
请根据用户要求，创造一个完整的科幻小说初始设定，包括引人入胜的标题、世界观、主角设定。
要求设定具有科学性、想象力，能够支撑一个精彩的科幻故事。"""

            user_prompt_template = """请为我创建一个完整的科幻小说初始设定。

要求包含：
1. 一个引人入胜的小说标题
2. 简洁有力的小说简介（2-3句话）
3. 完整的科幻世界观设定（科技水平、太空设定、外星种族等）
4. 主角的详细信息（姓名、性格、背景、动机等）

整体设定要有内在逻辑，各部分要相互呼应。

{additional_requirements}"""

        return system_prompt, user_prompt_template

    async def generate_complete_novel(
        self,
        genre: NovelGenre,
        requirements: str = ""
    ) -> Dict[str, Any]:
        """
        生成完整的小说初始设定（标题+世界观+主角）

        Args:
            genre: 小说类型
            requirements: 额外要求

        Returns:
            包含完整小说设定的字典
        """
        try:
            system_prompt, user_template = self._get_complete_novel_prompts(genre)
            user_prompt = user_template.format(
                additional_requirements=requirements or "无特殊要求，请自由发挥创意。"
            )

            result = await kimi_service.generate_structured_output(
                model_class=NovelFullProfile,
                user_prompt=user_prompt,
                system_prompt=system_prompt
            )

            result["genre"] = genre.value
            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"生成完整小说设定异常: {str(e)}",
                "data": None,
                "genre": genre.value
            }

    async def generate_novel_foundation(
        self,
        genre: NovelGenre,
        world_requirements: str = "",
        protagonist_requirements: str = ""
    ) -> Dict[str, Any]:
        """
        生成小说基础信息（世界观 + 主角）

        Args:
            genre: 小说类型
            world_requirements: 世界观的额外要求
            protagonist_requirements: 主角的额外要求

        Returns:
            包含世界观和主角信息的字典
        """
        result = {
            "success": True,
            "genre": genre.value,
            "world_setting": None,
            "protagonist": None,
            "errors": []
        }

        try:
            # 1. 生成世界观
            world_system_prompt, world_user_template, world_model_class = self._get_world_setting_prompts(genre)
            world_user_prompt = world_user_template.format(
                additional_requirements=world_requirements or "无特殊要求，请自由发挥创意。"
            )

            world_result = await kimi_service.generate_structured_output(
                model_class=world_model_class,
                user_prompt=world_user_prompt,
                system_prompt=world_system_prompt
            )

            if world_result["success"]:
                result["world_setting"] = world_result["data"]
            else:
                result["errors"].append(f"世界观生成失败: {world_result['error']}")

            # 2. 生成主角信息（基于世界观）
            if result["world_setting"]:
                protagonist_system_prompt, protagonist_user_template = self._get_protagonist_prompts(genre)

                # 将世界观信息传递给主角生成
                world_background = result["world_setting"].get("background", "")
                protagonist_user_prompt = protagonist_user_template.format(
                    world_background=world_background,
                    additional_requirements=protagonist_requirements or "无特殊要求，请创造一个有趣的角色。"
                )

                protagonist_result = await kimi_service.generate_structured_output(
                    model_class=ProtagonistProfile,
                    user_prompt=protagonist_user_prompt,
                    system_prompt=protagonist_system_prompt
                )

                if protagonist_result["success"]:
                    result["protagonist"] = protagonist_result["data"]
                else:
                    result["errors"].append(f"主角生成失败: {protagonist_result['error']}")

            # 3. 判断整体是否成功
            if result["errors"]:
                result["success"] = len(result["errors"]) < 2  # 至少有一个成功

        except Exception as e:
            result["success"] = False
            result["errors"].append(f"生成过程异常: {str(e)}")

        return result

    async def generate_world_setting_only(
        self,
        genre: NovelGenre,
        requirements: str = ""
    ) -> Dict[str, Any]:
        """
        只生成世界观设定

        Args:
            genre: 小说类型
            requirements: 额外要求

        Returns:
            世界观生成结果
        """
        try:
            system_prompt, user_template, model_class = self._get_world_setting_prompts(genre)
            user_prompt = user_template.format(
                additional_requirements=requirements or "无特殊要求，请自由发挥创意。"
            )

            result = await kimi_service.generate_structured_output(
                model_class=model_class,
                user_prompt=user_prompt,
                system_prompt=system_prompt
            )

            result["genre"] = genre.value
            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"世界观生成异常: {str(e)}",
                "data": None,
                "genre": genre.value
            }

    async def generate_protagonist_only(
        self,
        genre: NovelGenre,
        world_background: str = "",
        requirements: str = ""
    ) -> Dict[str, Any]:
        """
        只生成主角信息

        Args:
            genre: 小说类型
            world_background: 世界观背景
            requirements: 额外要求

        Returns:
            主角生成结果
        """
        try:
            system_prompt, user_template = self._get_protagonist_prompts(genre)
            user_prompt = user_template.format(
                world_background=world_background or "通用背景设定",
                additional_requirements=requirements or "无特殊要求，请创造一个有趣的角色。"
            )

            result = await kimi_service.generate_structured_output(
                model_class=ProtagonistProfile,
                user_prompt=user_prompt,
                system_prompt=system_prompt
            )

            result["genre"] = genre.value
            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"主角生成异常: {str(e)}",
                "data": None,
                "genre": genre.value
            }


# 全局小说生成服务实例
novel_generator = NovelGeneratorService()