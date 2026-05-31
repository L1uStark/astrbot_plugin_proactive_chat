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
        # 强制日志，无论什么消息都输出
        logger.info(f"[调试] on_message 被触发")

        # 方法1: 通过 message_obj 获取消息类型
        msg_type = getattr(event.message_obj, 'message_type', None)
        logger.info(f"[调试] msg_type = {msg_type}")

        # 方法2: 通过 get_group_id 判断
        group_id = event.get_group_id()
        logger.info(f"[调试] group_id = {group_id}")

        # 方法3: 通过 get_sender_id 获取发送者
        sender_id = event.get_sender_id()
        logger.info(f"[调试] sender_id = {sender_id}")

        if msg_type == 'group':
            chat_type = "group"
            chat_id = str(group_id)
            if not self.config.get("group_enabled", True):
                logger.info(f"[调试] 群聊开关关闭，跳过")
                return
            allowed = self.config.get("group_allowed_ids", [])
            if allowed and chat_id not in [str(a) for a in allowed]:
                logger.info(f"[调试] 群 {chat_id} 不在白名单")
                return
        elif msg_type == 'private':
            chat_type = "private"
            chat_id = str(sender_id)
            if not self.config.get("private_enabled", True):
                logger.info(f"[调试] 私聊开关关闭，跳过")
                return
            allowed = self.config.get("private_allowed_ids", [])
            if allowed and chat_id not in [str(a) for a in allowed]:
                logger.info(f"[调试] 私聊 {chat_id} 不在白名单")
                return
        else:
            # 可能是输入状态、通知等，忽略
            logger.info(f"[调试] 无法识别的消息类型: {msg_type}，忽略")
            return

        # 注册会话
        self.proactive_scheduler.register_origin(chat_id, chat_type, event.unified_msg_origin)
        self.proactive_scheduler.on_message_received(chat_id, chat_type)

    async def terminate(self):
        logger.info("主动聊天插件正在卸载...")
        self.proactive_scheduler.stop()
        logger.info("主动聊天插件已卸载")
