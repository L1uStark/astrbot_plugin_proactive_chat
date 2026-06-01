import os
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from .proactive_scheduler import ProactiveScheduler

@register("proactive_chat", "L1uStark", "主动聊天插件，支持沉默触发、自我学习、连续发言限制", "1.4.0")
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

        # 获取原始消息，只要非空就视为有效消息
        raw_message = getattr(event.message_obj, 'message', [])
        if raw_message is None:
            return
        try:
            if len(raw_message) == 0:
                return
        except:
            return

        # 注册 origin（无论是否在时间段内，都需要保存 origin，否则时间段内找不到会话）
        self.proactive_scheduler.register_origin(chat_id, chat_type, event.unified_msg_origin)
        
        # 只有在允许时间段内收到消息，才更新计时
        if self.proactive_scheduler.is_in_time_window(chat_type):
            self.proactive_scheduler.on_message_received(chat_id, chat_type)
        else:
            logger.info(f"[日志] {chat_type} {chat_id} 在非允许时间段收到消息，已保存 origin 但不重置计时")

    async def terminate(self):
        logger.info("主动聊天插件正在卸载...")
        self.proactive_scheduler.stop()
        logger.info("主动聊天插件已卸载")
