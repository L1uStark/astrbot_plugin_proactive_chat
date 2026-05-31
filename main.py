import os
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from .proactive_scheduler import ProactiveScheduler

@register("proactive_chat", "L1uStark", "主动聊天插件，支持沉默触发、自我学习", "1.3.0")
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

        # 判断消息类型
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

        # 过滤输入状态：提取消息文本，若为空则忽略（不打断沉默）
        message_text = ""
        raw_message = getattr(event.message_obj, 'message', [])
        if isinstance(raw_message, list):
            for seg in raw_message:
                if isinstance(seg, dict) and seg.get('type') == 'text':
                    message_text += seg.get('data', {}).get('text', '')
        # 如果没有任何文字内容，说明是输入状态或其他通知，直接跳过
        if not message_text.strip():
            logger.info(f"[调试] {chat_type} {chat_id} 空消息（输入状态），忽略")
            return

        # 注册会话并记录消息时间
        self.proactive_scheduler.register_origin(chat_id, chat_type, event.unified_msg_origin)
        self.proactive_scheduler.on_message_received(chat_id, chat_type)

    async def terminate(self):
        logger.info("主动聊天插件正在卸载...")
        self.proactive_scheduler.stop()
        logger.info("主动聊天插件已卸载")
