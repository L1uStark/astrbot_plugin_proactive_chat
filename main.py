import os
from astrbot.core import register, Plugin, Context
from astrbot.core.message.event import MessageEvent
from .proactive_scheduler import ProactiveScheduler

@register("proactive_chat", "YourName", "主动聊天插件", "1.0.0", "https://github.com/yourname/astrbot_plugin_proactive_chat")
class ProactiveChatPlugin(Plugin):
    def __init__(self, context: Context, config: dict):
        super().__init__(context, config)
        self.config = config
        self.scheduler = ProactiveScheduler(self)
        self.scheduler.start()
    
    def get_resource_path(self, relative_path: str) -> str:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, relative_path)
    
    async def on_message(self, event: MessageEvent):
        session_id = event.get_session_id()
        if not session_id:
            return
        
        # 判断是群聊还是私聊（根据事件属性调整）
        # 常见适配器中：event.group_id 存在且非空表示群聊
        is_group = hasattr(event, 'group_id') and event.group_id is not None
        chat_type = "group" if is_group else "private"
        
        self.scheduler.register_origin(session_id, chat_type, event.unified_msg_origin)
        is_self = hasattr(event, 'is_send_by_self') and event.is_send_by_self()
        self.scheduler.record_message_time(session_id, chat_type, is_bot_message=is_self)
    
    async def on_plugin_load(self):
        self.logger.info("主动聊天插件已加载（支持群聊/私聊分离+自定义人格）")
    
    async def on_plugin_unload(self):
        self.scheduler.stop()
        self.logger.info("主动聊天插件已卸载")
