import os
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from .proactive_scheduler import ProactiveScheduler

@register("proactive_chat", "L1uStark", "主动聊天插件，支持沉默触发、自我学习", "1.2.0")
class ProactiveChatPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.proactive_scheduler = ProactiveScheduler(self)
        self.proactive_scheduler.start()
        logger.info("主动聊天插件已初始化！")

    def get_resource_path(self, relative_path: str) -> str:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, relative_path)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        group_id = str(event.get_group_id() or "").strip()
        sender_id = str(event.get_sender_id() or "").strip()

        if group_id:
            chat_type = "group"
            chat_id = group_id
            if not self.config.get("group_enabled", True):
                return
            allowed = self.config.get("group_allowed_ids", [])
            if allowed and chat_id not in [str(a) for a in allowed]:
                return
        elif sender_id:
            chat_type = "private"
            chat_id = sender_id
            if not self.config.get("private_enabled", True):
                return
            allowed = self.config.get("private_allowed_ids", [])
            if allowed and chat_id not in [str(a) for a in allowed]:
                return
        else:
            return

        self.proactive_scheduler.register_origin(chat_id, chat_type, event.unified_msg_origin)
        self.proactive_scheduler.on_message_received(chat_id, chat_type)

    async def terminate(self):
        logger.info("主动聊天插件正在卸载...")
        self.proactive_scheduler.stop()
        logger.info("主动聊天插件已卸载")
