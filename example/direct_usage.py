"""
@FileName: direct_usage.py
@Description: 作为Python库直接使用
@Author: HiPeng
@Github: https://github.com/neopen/video-shot-agent
@Time: 2026/2/10 19:46
"""
import asyncio

from penshot.api import PenshotFunction
from penshot.neopen import ShotConfig
from penshot.neopen.shot_language import Language
from penshot.neopen.task.task_manager import TaskManager


async def basic_usage():
    """基础用法示例"""
    print("=== 基础用法示例 ===")

    # 创建智能体实例
    agent = PenshotFunction(language=Language.ZH)

    script = """
    场景：现代办公室
    时间：下午3点
    人物：小李（程序员）
    动作：小李正在写代码，突然接到电话，表情惊讶
    """

    # 同步调用（等待完成）
    result = agent.breakdown_script(script)

    print(f"任务ID: {result.task_id}")
    print(f"成功: {result.success}")
    print(f"状态: {result.status}")

    if result.success:
        data = result.data or {}
        shots = data.get("shots", [])
        stats = data.get("stats", {})
        print(f"镜头数量: {stats.get('shot_count', len(shots))}")
        print(f"总时长: {stats.get('total_duration', 0):.1f}秒")

        # 显示前3个镜头
        for i, shot in enumerate(shots[:3], 1):
            print(f"  镜头{i}: {shot.get('description', '')[:50]}...")

    return result


async def async_usage():
    """异步用法示例"""
    print("\n=== 异步用法示例 ===")

    agent = PenshotFunction(language=Language.ZH)

    script = """
    早晨，一个女孩在咖啡馆读书，阳光透过窗户...
    """

    # 异步提交任务
    task_id = agent.breakdown_script_async(
        script,
        callback=lambda r: print(f"回调: 任务 {r.task_id} 完成")
    )

    print(f"任务已提交: {task_id}")

    # 查询状态
    status = agent.get_task_status(task_id)
    print(f"初始状态: {status.get('status')}")

    # 等待结果
    result = await agent.wait_for_result_async(task_id)

    print(f"最终结果: 成功={result.success}, 状态={result.status}")

    return result


async def batch_processing():
    """批量处理示例"""
    print("\n=== 批量处理示例 ===")

    agent = PenshotFunction(language=Language.ZH)

    scripts = [
        "一个男人在海边跑步，日出时分...",
        "两个孩子在游乐场玩耍，欢声笑语...",
        "老人在公园下棋，专注沉思..."
    ]

    # 同步批量处理
    results = agent.batch_breakdown(scripts)

    for i, result in enumerate(results, 1):
        if result.success:
            data = result.data or {}
            shots = data.get("shots", [])
            print(f"任务 {i}: 成功, {len(shots)}个镜头")
        else:
            print(f"任务 {i}: 失败 - {result.error}")

    return results


async def async_batch_processing():
    """异步批量处理示例"""
    print("\n=== 异步批量处理示例 ===")

    agent = PenshotFunction(language=Language.ZH)

    scripts = [
        "科幻场景：太空站内部，宇航员发现异常信号...",
        "古装场景：侠客在竹林中对决...",
        "动画场景：小动物在森林里探险..."
    ]

    # 异步批量处理
    results = await agent.batch_breakdown_async(scripts, max_concurrent=2)

    for i, result in enumerate(results, 1):
        if result.success:
            data = result.data or {}
            stats = data.get("stats", {})
            print(f"任务 {i}: 成功, {stats.get('shot_count', 0)}个镜头, {result.processing_time_ms}ms")
        else:
            print(f"任务 {i}: 失败 - {result.error}")

    return results


async def with_custom_config():
    """使用自定义配置"""
    print("\n=== 自定义配置示例 ===")

    # 创建自定义配置
    custom_config = ShotConfig(
        model_name="gpt-4",
        temperature=0.3,
        max_tokens=3000
    )

    agent = PenshotFunction(
        config=custom_config,
        language=Language.ZH
    )

    script = "科幻场景：太空站内部，宇航员发现异常信号..."

    result = agent.breakdown_script(script)

    print(f"使用自定义配置: 成功={result.success}")

    return result


async def with_task_manager():
    """使用共享任务管理器示例"""
    print("\n=== 共享任务管理器示例 ===")

    # 创建共享任务管理器
    task_manager = TaskManager()

    # 创建多个智能体共享同一个任务管理器
    agent1 = PenshotFunction(task_manager=task_manager)
    agent2 = PenshotFunction(task_manager=task_manager)

    # 提交任务
    task_id1 = agent1.breakdown_script_async("第一个剧本...")
    task_id2 = agent2.breakdown_script_async("第二个剧本...")

    print(f"任务1: {task_id1}")
    print(f"任务2: {task_id2}")

    # 可以通过任一智能体查询状态
    status1 = agent1.get_task_status(task_id1)
    status2 = agent2.get_task_status(task_id2)

    print(f"任务1状态: {status1.get('status')}")
    print(f"任务2状态: {status2.get('status')}")

    # 等待所有任务完成
    results = await asyncio.gather(
        agent1.wait_for_result_async(task_id1),
        agent2.wait_for_result_async(task_id2)
    )

    return results


def main():
    """主函数演示各种用法"""

    # 基本用法（同步）
    result = asyncio.run(basic_usage())

    # 异步用法
    # async_result = asyncio.run(async_usage())

    # 批量处理
    # batch_results = asyncio.run(batch_processing())

    # 异步批量处理
    # async_batch_results = asyncio.run(async_batch_processing())

    # 自定义配置
    # custom_result = asyncio.run(with_custom_config())

    # 共享任务管理器
    # shared_results = asyncio.run(with_task_manager())


if __name__ == "__main__":
    main()
