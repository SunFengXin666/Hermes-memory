User communicates primarily in Chinese (zh-CN). They use Tencent Cloud (腾讯云) servers with security groups that block inbound ports by default. Their server has limited external network access (ghcr.io and Docker Hub connections time out frequently).
§
Chinese-speaking user (conversations in Chinese). Runs Hermes Agent on a Tencent Cloud server (49.232.224.90, ap-beijing). Has QQ Bot bound to Hermes (app_id 1903820137). Uses SSH for server management. Has both Flask web panel (port 3000) and official Hermes Dashboard (port 9119) deployed.
§
User demands extremely concise responses — every character costs money (QQ bot message costs). No pleasantries, no fluff, get straight to the point.
§
用户QQ号：3240171077。可通过NapCat QQ Bot发消息到该QQ（ws://127.0.0.1:3001，send_private_msg）。
§
QQ用户，番茄作家网(fanqienovel.com)作者，手机号15601447368。需登录后台管理章节。
§
用户想要多 agent 编排——我拆任务，派专门职责的子 agent（图像/代码/测试等），我汇总。图像 agent 流程：收到图→spawn只带vision+file的子agent分析→结果给我处理。我是总控角色。
§
When reporting vision model analysis, flag uncertain descriptions as guesses — don't state "possibly/maybe" items as facts. User will correct if wrong.