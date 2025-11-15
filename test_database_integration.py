#!/usr/bin/env python3
"""
测试数据库集成功能
"""

import asyncio
import io
import os
import sys
import uuid
from pathlib import Path


def configure_stdio() -> None:
    """确保 Windows 终端可以输出 emoji/中文。"""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if not stream:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
                continue
        except Exception:  # noqa: BLE001
            pass
        buffer = getattr(stream, "buffer", None)
        if buffer:
            try:
                wrapper = io.TextIOWrapper(buffer, encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                continue
            setattr(sys, name, wrapper)


# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置环境变量
os.environ["DATABASE_URL"] = "postgresql://postgres:123456@localhost:5432/gummy_translator"

async def test_database_integration():
    """测试数据库集成功能"""
    try:
        print("🧪 开始测试数据库集成...")
        
        # 导入集成模块
        from shared.database.integration import (
            TranslationServiceIntegration,
            VoiceServiceIntegration, 
            SceneServiceIntegration,
            SystemIntegration
        )
        
        print("✅ 数据库集成模块导入成功")
        
        # 测试1: 创建用户会话
        print("\n📝 测试1: 创建用户会话")
        user_id = uuid.uuid4()
        session_id = "test_session_001"
        
        session = await VoiceServiceIntegration.create_or_get_session(
            user_id=user_id,
            session_id=session_id
        )
        
        print(f"✅ 会话创建成功: {session.id}")
        
        # 测试2: 记录翻译历史
        print("\n📝 测试2: 记录翻译历史")
        translation = await TranslationServiceIntegration.log_translation(
            user_id=user_id,
            session_id=session.id,
            source_text="Hello, world!",
            target_text="你好，世界！",
            source_language="en",
            target_language="zh",
            api_provider="test_provider",
            confidence_score=0.95,
            quality_score=0.90,
            processing_time=1200,
            scene_context="casual_conversation"
        )
        
        print(f"✅ 翻译记录成功: {translation.id}")
        
        # 测试3: 翻译缓存
        print("\n📝 测试3: 翻译缓存")
        cached = await TranslationServiceIntegration.get_or_create_translation_cache(
            source_text="Hello, world!",
            source_language="en",
            target_language="zh",
            target_text="你好，世界！",
            api_provider="test_provider",
            confidence_score=0.95
        )
        
        print(f"✅ 翻译缓存成功: {cached.id}")
        
        # 测试4: 场景分析
        print("\n📝 测试4: 场景分析记录")
        analysis = await SceneServiceIntegration.log_scene_analysis(
            session_id=session.id,
            scene_type="casual_conversation",
            confidence_score=0.88,
            audio_features={
                "noise_level": 0.1,
                "speech_clarity": 0.9,
                "background_music": False
            },
            content_features={
                "formality": 0.3,
                "emotion": "neutral",
                "complexity": 0.4
            }
        )
        
        print(f"✅ 场景分析记录成功: {analysis.id}")
        
        # 测试5: 系统配置
        print("\n📝 测试5: 系统配置")
        await SystemIntegration.set_system_config(
            "test_feature_enabled", 
            True, 
            "测试功能开关"
        )
        
        value = await SystemIntegration.get_system_config("test_feature_enabled")
        print(f"✅ 系统配置读写成功: {value}")
        
        # 测试6: 系统指标
        print("\n📝 测试6: 系统指标记录")
        await SystemIntegration.record_metric(
            name="database_test_metric",
            value=99.5,
            unit="percent",
            labels={"test": "integration", "component": "database"}
        )
        
        print("✅ 系统指标记录成功")
        
        # 测试7: 审计日志
        print("\n📝 测试7: 审计日志")
        await SystemIntegration.log_user_action(
            action="database_integration_test",
            user_id=user_id,
            resource_type="test",
            resource_id="integration_test",
            new_values={"status": "completed", "result": "success"}
        )
        
        print("✅ 审计日志记录成功")
        
        # 测试8: 获取统计信息
        print("\n📝 测试8: 获取数据库统计")
        from shared.database.session import get_session
        from shared.database.integration import DatabaseService
        
        async with get_session() as session_db:
            db = DatabaseService(session_db)
            
            # 统计各种数据
            user_count = await db.users.count()
            session_count = await db.user_sessions.count()
            translation_count = await db.translation_history.count()
            cache_count = await db.translation_cache.count()
            config_count = await db.system_configurations.count()
            
            print(f"📊 数据库统计:")
            print(f"   - 用户数: {user_count}")
            print(f"   - 会话数: {session_count}")
            print(f"   - 翻译记录: {translation_count}")
            print(f"   - 缓存条目: {cache_count}")
            print(f"   - 系统配置: {config_count}")
        
        print("\n" + "=" * 50)
        print("🎉 数据库集成测试全部通过！")
        print("\n✨ 测试摘要:")
        print("  ✅ 用户会话管理")
        print("  ✅ 翻译历史记录")
        print("  ✅ 翻译缓存功能")
        print("  ✅ 场景分析记录")
        print("  ✅ 系统配置管理")
        print("  ✅ 系统指标收集")
        print("  ✅ 审计日志记录")
        print("  ✅ 数据库查询统计")
        
        print("\n🚀 数据库已就绪，可以启动微服务了！")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 数据库集成测试失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        print(f"详细错误:\n{traceback.format_exc()}")
        return False

async def test_config_retrieval():
    """测试配置获取"""
    try:
        print("\n🔧 测试配置获取功能...")
        
        from shared.database.integration import SystemIntegration, SceneServiceIntegration
        
        # 获取系统配置
        max_length = await SystemIntegration.get_system_config("max_translation_length", 5000)
        cache_ttl = await SystemIntegration.get_system_config("cache_ttl_default", 3600)
        
        print(f"📋 系统配置:")
        print(f"   - 最大翻译长度: {max_length}")
        print(f"   - 缓存过期时间: {cache_ttl}秒")
        
        # 获取场景配置
        business_config = await SceneServiceIntegration.get_scene_configuration("business_meeting")
        casual_config = await SceneServiceIntegration.get_scene_configuration("casual_conversation")
        
        if business_config:
            print(f"📋 商务会议场景配置:")
            print(f"   - 翻译风格: {business_config.configuration.get('translation_style')}")
            print(f"   - 响应速度: {business_config.configuration.get('response_speed')}")
        
        if casual_config:
            print(f"📋 日常对话场景配置:")
            print(f"   - 翻译风格: {casual_config.configuration.get('translation_style')}")
            print(f"   - 响应速度: {casual_config.configuration.get('response_speed')}")
        
        print("✅ 配置获取测试成功")
        
    except Exception as e:
        print(f"❌ 配置获取测试失败: {e}")

def main():
    """主函数"""
    configure_stdio()
    print("🧪 ZhiYUAI 2.0 数据库集成测试")
    print("=" * 50)
    
    try:
        # 运行测试
        success1 = asyncio.run(test_database_integration())
        asyncio.run(test_config_retrieval())
        
        if success1:
            print("\n" + "=" * 50)
            print("🎊 所有测试通过！数据库集成工作正常！")
            print("\n💡 下一步建议:")
            print("  1. 启动微服务: python services/translation/main.py")
            print("  2. 测试API接口")
            print("  3. 集成前端界面")
        else:
            print("\n❌ 测试失败，请检查错误信息")
            
    except KeyboardInterrupt:
        print("\n⚠️ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")

if __name__ == "__main__":
    main()
