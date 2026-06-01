# Bot也想说说话 (Proactive Chat)

让机器人像真正的群友一样，在群聊或私聊中**主动打破沉默**。支持多阶段概率掷骰、连续发言限制、跨日时间段、自我学习、群私分离、自定义人格与独立 LLM。

## ✨ 主要功能

- **沉默触发**：每次有人发言后进入静默等待，只有彻底沉默一段时间后，机器人才可能主动发言。
- **多阶段掷骰**：第一阶段窗口内以较低概率掷骰，超时后进入第二阶段，概率提升；超过第二阶段则强制发言。
- **连续发言限制**：可分别设置群聊/私聊连续主动发言最大次数，达到后暂停计时，直到新消息才重新开始。
- **跨日时间段**：允许发言时间支持跨日，例如 22:00 - 02:00。
- **自我学习**（仅白名单群）：每天凌晨自动分析过去24小时聊天记录，动态调整沉默时间、窗口时长和概率，并收集群友的说话风格作为参考。
- **自定义人格 & LLM**：支持独立 LLM 或回退到系统默认，可自定义人设。
- **话题权重**：支持历史消息、知识/时间、预设话题、自定义话题四种来源，权重可按比例自适应。

## 📦 安装

将插件文件夹放入 `AstrBot/data/plugins/` 下，确保目录名为 `proactive_chat`，重启 AstrBot 即可。

## ⚙️ 配置说明

| 配置项 | 说明 |
|--------|------|
| `enabled` | 总开关 |
| `personality_custom` | 自定义人格描述 |
| `group_enabled` / `private_enabled` | 群聊/私聊开关 |
| `group_start_time` / `group_end_time` | 允许发言时间段，支持跨日 |
| `group_allowed_ids` / `private_allowed_ids` | 白名单 |
| `group_silence_wait` / `private_silence_wait` | 静默等待时间（分钟） |
| `group_phase1_duration` / `private_phase1_duration` | 第一阶段窗口时长 |
| `group_phase1_prob` / `private_phase1_prob` | 第一阶段触发概率 |
| `group_phase2_duration` / `private_phase2_duration` | 第二阶段窗口时长 |
| `group_phase2_prob` / `private_phase2_prob` | 第二阶段触发概率 |
| `group_check_interval` / `private_check_interval` | 掷骰检查间隔（分钟） |
| `group_max_consecutive_speaks` / `private_max_consecutive_speaks` | 连续主动发言最大次数（0=不限） |
| `weight_history` 等 | 四种话题权重 |
| `llm_provider` 等 | LLM 配置，留空使用系统默认 |

## 🧠 学习机制

每天凌晨 3 点自动学习白名单群的沉默间隔和例句，动态调整参数，可在 `learning_status` 只读文本框查看结果。

## 🧪 测试建议

1. 设置 `silence_wait=2`, `phase1_prob=0.9` 快速验证触发逻辑。
2. 在白名单中添加测试群，停止发言后观察机器人是否主动说话。
3. 设置跨日时间段（如 22:00-02:00）测试夜间是否生效。

## 📜 版本

- v1.4.0：支持跨日时间段、连续发言限制、消息过滤修复、日志统一
- v1.3.x：多阶段概率掷骰、静默触发、自我学习
- v1.0.0：初始主动发言功能

---

**作者：L1uStark**
