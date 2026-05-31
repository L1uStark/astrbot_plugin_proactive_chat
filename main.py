import os
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from .proactive_scheduler import ProactiveScheduler

@register("proactive_chat", "L1uStark", "主动聊天插件，支持沉默触发、自我学习", "1.3.2")
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

        # 获取原始消息
        raw_message = getattr(event.message_obj, 'message', [])
        if not isinstance(raw_message, list) or len(raw_message) == 0:
            logger.info(f"[调试] {chat_type} {chat_id} 空消息或输入状态，忽略")
            return

        # 提取所有消息段的类型，用于日志输出
        seg_types = []
        has_content = False
        for seg in raw_message:
            if isinstance(seg, dict):
                seg_type = seg.get('type', 'unknown')
                seg_types.append(seg_type)
                # 统一转小写判断，兼容所有大小写变体
                seg_type_lower = seg_type.lower()
                if seg_type_lower in ('text', 'plain', 'image', 'at', 'reply', 'face', 'video', 'file', 'audio', 'record'):
                    has_content = True
            else:
                seg_types.append(str(type(seg).__name__))

        # 打印消息段类型，便于排查
        logger.info(f"[调试] {chat_type} {chat_id} 消息段类型: {seg_types}")

        if not has_content:
            logger.info(f"[调试] {chat_type} {chat_id} 无有效内容（输入状态等），忽略")
            return

        # 注册会话并记录消息时间
        self.proactive_scheduler.register_origin(chat_id, chat_type, event.unified_msg_origin)
        self.proactive_scheduler.on_message_received(chat_id, chat_type)

    async def terminate(self):
        logger.info("主动聊天插件正在卸载...")
        self.proactive_scheduler.stop()
        logger.info("主动聊天插件已卸载")
