import os
import random
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api import logger
from astrbot.api.message_components import Plain
from .proactive_scheduler import ProactiveScheduler

@register("proactive_chat", "YourName", "让机器人主动发起聊天，支持群聊/私聊分离、自定义人格...", "1.0.0", "https://github.com/yourname/astrbot_plugin_proactive_chat")
class ProactiveChatPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.proactive_scheduler = ProactiveScheduler(self)
        # 在插件启动时启动调度器
        self.proactive_scheduler.start()

    def get_resource_path(self, relative_path: str) -> str:
        """获取资源文件的绝对路径"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, relative_path)

    async def terminate(self):
        '''当插件被卸载/停用时调用，用于清理资源。'''
        logger.info("主动聊天插件正在卸载...")
        self.proactive_scheduler.stop()
        logger.info("主动聊天插件已卸载")
