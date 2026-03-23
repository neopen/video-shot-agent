"""
@FileName: neopen_demo.py
@Description: 
@Author: HiPeng
@Time: 2026/3/23 19:04
"""
from penshot.api import PenshotFunction

# 其他智能体调用示例

# 创建智能体实例
agent = PenshotFunction()

# 方式1：同步调用（等待完成）
result = agent.breakdown_script(
    "深夜，客厅里，张三紧张地环顾四周..."
)
if result.success:
    print(f"生成 {result.data['stats']['shot_count']} 个镜头")
else:
    print(f"失败: {result.error}")

# 方式2：异步调用
task_id = agent.breakdown_script_async(
    "剧本内容",
    callback=lambda r: print(f"任务完成: {r.task_id}")
)

# 方式3：查询状态
status = agent.get_task_status(task_id)
print(f"状态: {status['status']}, 进度: {status.get('progress')}%")

# 方式4：等待结果
result = agent.wait_for_result(task_id)
print(result.data)

# 方式5：批量处理
results = agent.batch_breakdown(["剧本1", "剧本2", "剧本3"])
for r in results:
    print(f"{r.task_id}: {'成功' if r.success else '失败'}")