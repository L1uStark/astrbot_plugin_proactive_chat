import logging
from typing import Literal

logger = logging.getLogger(__name__)

ChatType = Literal["group", "private"]

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None
try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None

class LLMClient:
    def __init__(self, config: dict, system_personality: str):
        self.config = config
        self.system_personality = system_personality
        self.provider = config.get("llm_provider", "")
        self.api_key = config.get("llm_api_key", "")
        self.base_url = config.get("llm_base_url", "")
        self.model = config.get("llm_model", "gpt-3.5-turbo")
        
        self.client = None
        if self.provider and self.api_key:
            try:
                self._init_client()
                logger.info(f"独立 LLM 客户端初始化成功: provider={self.provider}, model={self.model}")
            except Exception as e:
                logger.error(f"独立 LLM 客户端初始化失败: {e}")
                self.client = None
        else:
            logger.info("未配置独立 LLM API Key，将使用系统默认 LLM")
    
    def _init_client(self):
        if self.provider in ["openai", "deepseek", "custom"]:
            if AsyncOpenAI is None:
                raise ImportError("请安装 openai: pip install openai")
            base = self.base_url if self.base_url else None
            if self.provider == "deepseek" and not base:
                base = "https://api.deepseek.com"
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=base)
        elif self.provider == "anthropic":
            if AsyncAnthropic is None:
                raise ImportError("请安装 anthropic: pip install anthropic")
            self.client = AsyncAnthropic(api_key=self.api_key)
        else:
            raise ValueError(f"不支持的 provider: {self.provider}")
    
    async def generate_response(self, topic_prompt: str, chat_type: ChatType) -> str:
        """
        根据话题提示生成主动聊天消息
        topic_prompt: 话题描述（例如“聊一聊最近的热点新闻”或“根据历史消息：...”
        """
        if not self.client:
            raise ValueError("LLM 客户端未初始化或配置错误")
        
        audience = "大家" if chat_type == "group" else "你"
        
        system_prompt = (
            f"你是一个聊天机器人，你的人设是：{self.system_personality}\n"
            f"请严格遵循以下要求：\n"
            f"1. 根据话题提示生成一句自然的主动聊天消息，对象是{audience}。\n"
            f"2. 语气贴合人设，不要提及自己是AI。\n"
            f"3. 语言简短自然，不超过50字。\n"
            f"4. 只输出消息内容，不要加任何引号或额外说明。"
        )
        user_prompt = f"话题提示：{topic_prompt}\n请生成主动聊天消息："
        
        try:
            if self.provider == "anthropic":
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=100,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                result = response.content[0].text.strip()
            else:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=100
                )
                result = response.choices[0].message.content.strip()
            
            logger.info(f"LLM 生成成功: {result[:50]}...")
            return result
        except Exception as e:
            logger.error(f"LLM 生成失败: {type(e).__name__}: {str(e)}")
            raise
