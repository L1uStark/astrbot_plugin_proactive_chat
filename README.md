# Bot也想说说话 (Proactive Chat)

让机器人像真正的群友一样，在群聊或私聊中**主动打破沉默**。支持多阶段概率掷骰、连续发言限制、自我学习、群私分离、自定义人格与独立 LLM。

## ✨ 主要功能

- **沉默触发**：每次有人发言后进入静默等待，只有彻底沉默一段时间后，机器人才可能主动发言。
- **多阶段掷骰**：第一阶段窗口内以较低概率掷骰，若超时则进入第二阶段，概率提升；超过第二阶段则强制发言。
- **连续发言限制**：可设置连续发言最大次数，达到后暂停计时，直到新消息才重新开始。
- **自我学习**（仅白名单群）：每天凌晨自动分析过去24小时聊天记录，动态调整沉默时间、窗口时长和概率，并收集群友的说话风格作为参考。
- **自定义人格 & LLM**：支持独立 LLM 或回退到系统默认，可自定义人设。
- **话题权重**：支持历史消息、知识/时间、预设话题、自定义话题四种来源，权重可按比例自适应。
- **群聊/私聊完全分离**：各自独立的开关、时间窗口、白名单、概率、连续发言上限等。

## 📦 安装

1. 将插件文件夹放入 `AstrBot/data/plugins/` 下，确保目录名为 `proactive_chat`。
2. 重启 AstrBot，或进入 WebUI 插件管理页面启用 `proactive_chat`。

## ⚙️ 配置说明（WebUI 可视化配置）

| 配置项 | 说明 |
|--------|------|
| `enabled` | 总开关 |
| `debug_log` | 是否输出详细调试日志 |
| `personality_custom` | 自定义人格描述 |
| `enable_context_history` | 是否读取历史消息 |
| **群聊/私聊独立配置** | |
| `group_enabled` / `private_enabled` | 群聊/私聊主动聊天开关 |
| `group_start_time` / `group_end_time` | 允许发言的时间段 |
| `group_allowed_ids` / `private_allowed_ids` | 群聊/私聊白名单 |
| `group_silence_wait` / `private_silence_wait` | 静默等待时间（分钟） |
| `group_phase1_duration` / `private_phase1_duration` | 第一阶段窗口时长（分钟） |
| `group_phase1_prob` / `private_phase1_prob` | 第一阶段触发概率（0~1） |
| `group_phase2_duration` / `private_phase2_duration` | 第二阶段窗口时长（分钟） |
| `group_phase2_prob` / `private_phase2_prob` | 第二阶段触发概率（0~1） |
| `group_check_interval` / `private_check_interval` | 掷骰子检查间隔（分钟） |
| `group_max_consecutive_speaks` / `private_max_consecutive_speaks` | 连续主动发言最大次数（0=不限） |
| **话题权重** | |
| `weight_history` / `weight_knowledge` / `weight_preset` / `weight_custom` | 四种话题来源的权重 |
| `custom_topics` | 自定义话题关键词列表 |
| **LLM 配置** | |
| `llm_provider` / `llm_api_key` / `llm_base_url` / `llm_model` | 独立 LLM 配置，留空则用系统默认 |
| `learning_status` | **只读**，展示最近一次学习状态 |

## 🧠 学习机制详解

- **触发时机**：每天凌晨 **03:00** 自动执行。
- **学习范围**：仅分析 `group_allowed_ids` 白名单中的群。
- **学习内容**：分析过去24小时非机器人消息的沉默间隔，动态调整 `silence_wait`、`phase1_duration`、`phase1_prob` 等参数；收集打破沉默的例句供风格参考。
- **可视化**：学习后 `learning_status` 文本框会显示当前动态参数和例句。

## ⚠️ 注意事项

- 只有新消息才会触发该插件，默认启动（包括重新设置保存之后）都不会。
- 检查循环每分钟运行一次，掷骰间隔可自定义（默认8分钟）。
- 仅支持 OneBot v11 (因为没测试过其他)。

## 🧪 初始化测试建议

1. 设置较短的 `silence_wait` (如 2 分钟) 和较高的 `phase1_prob` (0.9) 快速验证触发逻辑。
2. 在 `group_allowed_ids` 中填入测试群，发送几条消息后停止发言，观察机器人是否在静默后主动说话。
3. 查看 `learning_status` 文本框，确认每日学习是否正常运行。

## 🐛 常见问题

**Q：为什么机器人没有主动发言？**  
A：请检查是否满足所有条件：总开关、群/私聊开关、时间窗口、白名单、静默等待时间。将 `是否输出详细调试日志` 开启并查看日志。

**Q：学习功能不工作？**  
A：确保 `group_enabled` 已开启，且 `group_allowed_ids` 不为空（否则学习会自动跳过）。

**Q：我想完全使用系统默认 LLM，怎么设置？**  
A：将 `llm_provider` 和 `llm_api_key` 留空，插件会自动调用 AstrBot 配置好的 LLM。

## 📜 版本

- v1.4.0：新增连续发言限制、修复发送问题、优化日志
- v1.3.x：多阶段概率掷骰、静默触发、自我学习
- v1.0.0：初始主动发言功能

---

**作者：L1uStark**
