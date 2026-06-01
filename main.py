import os
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from .proactive_scheduler import ProactiveScheduler

# 所有会被认为是有效消息的段类型 (小写)
VALID_SEGMENT_TYPES = {
    'text', 'plain', 'image', 'at', 'reply', 'face',
    'video', 'file', 'audio', 'record', 'json', 'card'
}

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
        # 获取群号 / 发送者 QQ
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

        # 提取原始消息
        raw_message = getattr(event.message_obj, 'message', [])
        has_content = False
        seg_types = []

        # 情况1：标准的 list[dict] 格式
        if isinstance(raw_message, list) and len(raw_message) > 0:
            for seg in raw_message:
                if isinstance(seg, dict):
                    seg_type = seg.get('type', 'unknown')
                    seg_types.append(seg_type)
                    if seg_type.lower() in VALID_SEGMENT_TYPES:
                        has_content = True
                else:
                    seg_types.append(str(type(seg).__name__))
        # 情况2：可能是 AstrBot 的 MessageChain 对象，直接判断是否为空
        elif hasattr(raw_message, '__len__') and len(raw_message) > 0:
            has_content = True

        if has_content:
            # 注册并重置计时
            self.proactive_scheduler.register_origin(chat_id, chat_type, event.unified_msg_origin)
            self.proactive_scheduler.on_message_received(chat_id, chat_type)
        else:
            logger.info(f"[日志] {chat_type} {chat_id} 消息段类型: {seg_types}，无有效内容，忽略")

    async def terminate(self):
        logger.info("主动聊天插件正在卸载...")
        self.proactive_scheduler.stop()
        logger.info("主动聊天插件已卸载")
