"""
@FileName: penshot_config_demo.py
@Description: Penshot 配置示例
@Author: HiPeng
@Github: https://github.com/neopen/video-shot-agent
@Time: 2026/2/10 19:52
"""
import asyncio

from penshot.api import PenshotFunction
from penshot.neopen import ShotConfig
from penshot.neopen.shot_language import Language
from penshot.neopen.task.task_manager import TaskManager


class ConfigFactory:
    """配置工厂，方便创建不同用途的配置"""

    @staticmethod
    def create_fast_config() -> ShotConfig:
        """快速但简略的配置"""
        return ShotConfig(
            model_name="gpt-3.5-turbo",
            temperature=0.9,
            max_tokens=1000,
            timeout=15,
        )

    @staticmethod
    def create_quality_config() -> ShotConfig:
        """高质量详细配置"""
        return ShotConfig(
            model_name="gpt-4",
            temperature=0.4,
            max_tokens=5000,
            top_p=0.95,
            timeout=60,
        )

    @staticmethod
    def create_local_config(base_url: str = "http://localhost:11434/v1") -> ShotConfig:
        """本地模型配置"""
        return ShotConfig(
            model_name="qwen2.5:14b",
            base_url=base_url,
            temperature=0.7,
            max_tokens=3000,
            timeout=120,
        )

    @staticmethod
    def create_deepseek_config(api_key: str) -> ShotConfig:
        """DeepSeek 配置"""
        from pydantic import SecretStr
        return ShotConfig(
            model_name="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            api_key=SecretStr(api_key),
            temperature=0.6,
            max_tokens=4000,
        )


async def basic_config_demo():
    """基础配置示例"""
    print("=== 基础配置示例 ===")

    config = ShotConfig(
        model_name="gpt-4",
        temperature=0.7,
        max_tokens=2000
    )

    agent = PenshotFunction(config=config, language=Language.ZH)

    result = agent.breakdown_script("一个简单的测试场景")

    print(f"配置: model={config.model_name}, temperature={config.temperature}")
    print(f"结果: 成功={result.success}")

    return result


async def local_model_demo():
    """本地模型示例"""
    print("\n=== 本地模型示例 ===")

    try:
        config = ConfigFactory.create_local_config()
        agent = PenshotFunction(config=config, language=Language.ZH)

        result = agent.breakdown_script("本地模型测试场景")

        print(f"本地模型配置: {config.model_name}")
        print(f"结果: 成功={result.success}")

        return result

    except Exception as e:
        print(f"本地模型不可用: {e}")
        return None


async def quality_config_demo():
    """高质量配置示例"""
    print("\n=== 高质量配置示例 ===")

    config = ConfigFactory.create_quality_config()
    agent = PenshotFunction(config=config, language=Language.ZH)

    detailed_script = """
    电影《追光者》开场：

    第一场：黄昏，海边
    时间：傍晚6点，日落时分
    地点：东海市沙滩
    人物：林浩（25岁，摄影师）、苏晴（23岁，画家）

    内容：
    1. 远景：夕阳下的海滩，海鸥飞过
    2. 中景：林浩架设三脚架，调整相机参数
    3. 近景：苏晴在画板前作画，画笔特写
    4. 双人镜头：两人偶然对视，微笑
    5. 特写：相机取景器中的夕阳

    视觉要求：
    - 暖色调，金色阳光
    - 慢镜头处理海浪
    - 逆光拍摄剪影效果
    """

    result = agent.breakdown_script(detailed_script)

    if result.success:
        data = result.data or {}
        shots = data.get("shots", [])
        stats = data.get("stats", {})
        print(f"高质量配置结果:")
        print(f"  镜头数: {stats.get('shot_count', len(shots))}")
        print(f"  总时长: {stats.get('total_duration', 0):.1f}秒")

        for i, shot in enumerate(shots[:3], 1):
            print(f"  镜头{i}: {shot.get('description', '')[:60]}...")

    return result


async def fallback_config_demo():
    """降级配置示例"""
    print("\n=== 降级配置示例 ===")

    primary_config = ConfigFactory.create_quality_config()
    fallback_config = ConfigFactory.create_fast_config()

    agent = PenshotFunction(config=primary_config, language=Language.ZH)

    # 模拟主配置失败，使用降级配置
    try:
        result = agent.breakdown_script("测试剧本")

        if result.success:
            print("主配置成功")
        else:
            print(f"主配置失败: {result.error}")
            print("切换到降级配置...")

            agent_fallback = PenshotFunction(config=fallback_config, language=Language.ZH)
            result = agent_fallback.breakdown_script("测试剧本")
            print(f"降级配置结果: 成功={result.success}")

        return result

    except Exception as e:
        print(f"降级处理: {e}")
        return None


async def multi_config_demo():
    """多配置对比示例"""
    print("\n=== 多配置对比示例 ===")

    configs = {
        "快速模式": ConfigFactory.create_fast_config(),
        "高质量模式": ConfigFactory.create_quality_config(),
        "本地模式": ConfigFactory.create_local_config()
    }

    test_script = "一个人在房间里看书，阳光透过窗户"

    results = {}
    for name, config in configs.items():
        try:
            agent = PenshotFunction(config=config, language=Language.ZH)
            result = agent.breakdown_script(test_script)

            if result.success:
                data = result.data or {}
                shots = data.get("shots", [])
                stats = data.get("stats", {})
                results[name] = {
                    "success": True,
                    "shots": len(shots),
                    "duration": stats.get("total_duration", 0),
                    "processing_time": result.processing_time_ms
                }
            else:
                results[name] = {"success": False, "error": result.error}

        except Exception as e:
            results[name] = {"success": False, "error": str(e)}

    print("配置对比结果:")
    for name, result in results.items():
        if result["success"]:
            print(f"  {name}: {result['shots']}个镜头, {result['duration']:.1f}秒, {result['processing_time']}ms")
        else:
            print(f"  {name}: 失败 - {result.get('error')}")

    return results


async def shared_task_manager_demo():
    """共享任务管理器示例"""
    print("\n=== 共享任务管理器示例 ===")

    # 创建共享任务管理器
    task_manager = TaskManager()

    # 创建多个配置不同的智能体，但共享同一个任务管理器
    fast_agent = PenshotFunction(
        config=ConfigFactory.create_fast_config(),
        task_manager=task_manager,
        language=Language.ZH
    )

    quality_agent = PenshotFunction(
        config=ConfigFactory.create_quality_config(),
        task_manager=task_manager,
        language=Language.ZH
    )

    # 提交多个任务
    tasks = [
        fast_agent.breakdown_script_async("快速处理任务..."),
        quality_agent.breakdown_script_async("高质量处理任务..."),
        fast_agent.breakdown_script_async("另一个快速任务...")
    ]

    # 等待所有任务完成
    results = await asyncio.gather(
        *[fast_agent.wait_for_result_async(tid) for tid in tasks]
    )

    # 获取所有任务统计
    all_tasks = task_manager.get_all_tasks() if hasattr(task_manager, 'get_all_tasks') else []

    print(f"总任务数: {len(all_tasks)}")
    for i, result in enumerate(results, 1):
        print(f"  任务{i}: 成功={result.success}")

    return results


async def main():
    """主函数"""

    # 基础配置示例
    await basic_config_demo()

    # 本地模型示例
    await local_model_demo()

    # 高质量配置示例
    await quality_config_demo()

    # 降级配置示例
    await fallback_config_demo()

    # 多配置对比
    await multi_config_demo()

    # 共享任务管理器
    await shared_task_manager_demo()


if __name__ == "__main__":
    asyncio.run(main())
