"""
@FileName: neopen_demo.py
@Description: Penshot 智能体使用示例
@Author: HiPeng
@Time: 2026/3/23 19:04
"""
from penshot.api import PenshotFunction


def demo_sync():
    """同步调用示例"""
    print("=== 同步调用示例 ===")

    # 创建智能体实例（可配置并发数）
    agent = PenshotFunction(max_concurrent=5)

    # 同步调用（等待完成）
    result = agent.breakdown_script(
        "深夜，客厅里，张三紧张地环顾四周..."
    )

    if result.success:
        data = result.data or {}
        stats = data.get("stats", {})
        print(f"任务ID: {result.task_id}")
        print(f"成功: {result.success}")
        print(f"生成 {stats.get('shot_count', 0)} 个镜头")
        print(f"总时长: {stats.get('total_duration', 0):.1f}秒")
    else:
        print(f"失败: {result.error}")

    return result


def demo_async():
    """异步调用示例"""
    print("\n=== 异步调用示例 ===")

    agent = PenshotFunction(max_concurrent=5)

    def on_complete(r):
        print(f"回调: 任务 {r.task_id} 完成, 成功={r.success}")

    # 异步调用
    task_id = agent.breakdown_script_async(
        "剧本内容",
        callback=on_complete
    )
    print(f"任务已提交: {task_id}")

    # 查询状态
    status = agent.get_task_status(task_id)
    print(f"状态: {status['status']}, 进度: {status.get('progress', 0)}%")

    # 等待结果
    result = agent.wait_for_result(task_id)
    print(f"等待结果: 成功={result.success}")

    return result


def demo_batch():
    """批量处理示例"""
    print("\n=== 批量处理示例 ===")

    agent = PenshotFunction(max_concurrent=5)

    scripts = [
        "剧本1: 一个男人在海边跑步...",
        "剧本2: 两个孩子玩耍...",
        "剧本3: 老人下棋..."
    ]

    # 批量处理
    results = agent.batch_breakdown(scripts)

    for i, r in enumerate(results, 1):
        if r.success:
            data = r.data or {}
            stats = data.get("stats", {})
            print(f"任务{i}: 成功, 镜头数={stats.get('shot_count', 0)}")
        else:
            print(f"任务{i}: 失败 - {r.error}")

    return results


def demo_queue_status():
    """队列状态示例"""
    print("\n=== 队列状态示例 ===")

    agent = PenshotFunction(max_concurrent=2)

    # 查看队列状态
    queue_status = agent.get_queue_status()
    print(f"队列状态: 长度={queue_status['queue_length']}, 活跃={queue_status['active_tasks']}, 最大并发={queue_status['max_concurrent']}")

    # 查看统计信息
    stats = agent.get_stats()
    print(f"统计信息: 总提交={stats['total_submitted']}, 完成={stats['total_completed']}, 失败={stats['total_failed']}")

    return stats


def main():
    """主函数"""

    # 同步调用示例
    demo_sync()

    # 异步调用示例
    demo_async()

    # 批量处理示例
    demo_batch()

    # 队列状态示例
    demo_queue_status()


if __name__ == "__main__":
    main()
