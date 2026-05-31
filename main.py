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
        # 通过 message_obj 的 message_type 来判断群聊还是私聊
        msg_type = getattr(event.message_obj, 'message_type', None)
        
        if msg_type == 'group':
            chat_type = "group"
            chat_id = str(event.get_group_id())
            # 检查开关和白名单
            if not self.config.get("group_enabled", True):
                logger.info(f"[调试] 群聊主动聊天已关闭，跳过群 {chat_id}")
                return
            allowed = self.config.get("group_allowed_ids", [])
            if allowed and chat_id not in [str(a) for a in allowed]:
                logger.info(f"[调试] 群 {chat_id} 不在白名单，跳过")
                return
        elif msg_type == 'private':
            chat_type = "private"
            chat_id = str(event.get_sender_id())
            # 检查开关和白名单
            if not self.config.get("private_enabled", True):
                logger.info(f"[调试] 私聊主动聊天已关闭，跳过 {chat_id}")
                return
            allowed = self.config.get("private_allowed_ids", [])
            if allowed and chat_id not in [str(a) for a in allowed]:
                logger.info(f"[调试] 私聊 {chat_id} 不在白名单，跳过")
                return
        else:
            # 不是群聊也不是私聊（比如输入状态、通知等），直接忽略
            return

        # 注册会话 origin
        self.proactive_scheduler.register_origin(chat_id, chat_type, event.unified_msg_origin)
        # 任何消息都重置沉默（包括机器人自己）
        self.proactive_scheduler.on_message_received(chat_id, chat_type)

    async def terminate(self):
        logger.info("主动聊天插件正在卸载...")
        self.proactive_scheduler.stop()
        logger.info("主动聊天插件已卸载")
