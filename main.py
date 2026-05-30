import os
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from .proactive_scheduler import ProactiveScheduler

@register("proactive_chat", "YourName", "让机器人主动发起聊天，支持群聊/私聊分离、自定义人格...", "1.0.0", "https://github.com/yourname/astrbot_plugin_proactive_chat")
class ProactiveChatPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config  # 插件配置已自动注入
        self.proactive_scheduler = ProactiveScheduler(self)
        self.proactive_scheduler.start()
        logger.info("主动聊天插件已初始化！")

    def get_resource_path(self, relative_path: str) -> str:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, relative_path)

    # 监听所有消息，用于记录会话和 origin
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        session_id = event.get_session_id()
        if not session_id:
            return

        # 判断是群聊还是私聊
        is_group = event.get_group_id() is not None
        chat_type = "group" if is_group else "private"

        # 存储 origin 用于主动发送
        self.proactive_scheduler.register_origin(session_id, chat_type, event.unified_msg_origin)

        # 记录消息时间（排除机器人自己发出的）
        is_self = str(event.get_sender_id()) == str(event.get_self_id())
        self.proactive_scheduler.record_message_time(session_id, chat_type, is_bot_message=is_self)

    async def terminate(self):
        logger.info("主动聊天插件正在卸载...")
        self.proactive_scheduler.stop()
        logger.info("主动聊天插件已卸载")
