#!/usr/bin/env python3
"""
安装依赖并初始化数据库的完整脚本
"""

import os
import sys
import subprocess
import asyncio
from pathlib import Path

def install_packages():
    """安装必要的包"""
    packages = [
        "sqlalchemy[asyncio]",
        "asyncpg", 
        "psycopg2-binary",
        "pydantic",
        "fastapi",
        "uvicorn",
        "python-dotenv",
        "structlog"
    ]
    
    print("📦 安装必要的Python包...")
    for package in packages:
        print(f"安装 {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ {package} 安装成功")
        except subprocess.CalledProcessError as e:
            print(f"❌ {package} 安装失败: {e}")
            return False
    
    print("✅ 所有依赖包安装完成")
    return True

async def setup_database():
    """设置数据库"""
    try:
        print("🚀 开始数据库初始化...")
        
        # 现在导入模块
        print("📦 导入模块...")
        import sqlalchemy
        from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Boolean, DateTime, Text, UUID, DECIMAL, ForeignKey
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy.orm import declarative_base, relationship
        from sqlalchemy.sql import func
        from sqlalchemy.dialects.postgresql import JSONB, INET
        import uuid
        from datetime import datetime
        
        print("✅ 模块导入成功")
        
        # 创建数据库连接
        print("🔍 连接数据库...")
        database_url = "postgresql+asyncpg://postgres:123456@localhost:5432/gummy_translator"
        
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True
        )
        
        # 测试连接
        async with engine.begin() as conn:
            result = await conn.execute(sqlalchemy.text("SELECT 1"))
            assert result.scalar() == 1
        
        print("✅ 数据库连接成功")
        
        # 创建基础表结构
        print("🔨 创建数据库表...")
        
        # 定义 Base
        Base = declarative_base()
        
        # 用户表
        class User(Base):
            __tablename__ = "users"
            
            id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
            username = Column(String(50), unique=True, nullable=False, index=True)
            email = Column(String(100), unique=True, nullable=False, index=True)
            password_hash = Column(String(255), nullable=False)
            created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
            updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
            is_active = Column(Boolean, default=True, nullable=False)
            is_verified = Column(Boolean, default=False, nullable=False)
            profile = Column(JSONB, default={})
            preferences = Column(JSONB, default={})
            subscription_plan = Column(String(20), default="free", nullable=False)
            last_login = Column(DateTime(timezone=True))
        
        # 用户会话表
        class UserSession(Base):
            __tablename__ = "user_sessions"
            
            id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
            user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
            session_id = Column(String(255), unique=True, nullable=False, index=True)
            start_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
            end_time = Column(DateTime(timezone=True))
            duration = Column(Integer)
            scene_type = Column(String(50))
            language_pairs = Column(JSONB)
            quality_rating = Column(Integer)
            total_translations = Column(Integer, default=0, nullable=False)
            total_audio_duration = Column(Integer, default=0, nullable=False)
        
        # 翻译历史表
        class TranslationHistory(Base):
            __tablename__ = "translation_history"
            
            id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
            user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
            session_id = Column(UUID(as_uuid=True), ForeignKey("user_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
            source_text = Column(Text, nullable=False)
            target_text = Column(Text, nullable=False)
            source_language = Column(String(10), nullable=False, index=True)
            target_language = Column(String(10), nullable=False, index=True)
            confidence_score = Column(DECIMAL(3, 2))
            quality_score = Column(DECIMAL(3, 2))
            api_provider = Column(String(50), index=True)
            scene_context = Column(String(50))
            processing_time = Column(Integer)
            created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
        
        # 翻译缓存表
        class TranslationCache(Base):
            __tablename__ = "translation_cache"
            
            id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
            content_hash = Column(String(64), unique=True, nullable=False, index=True)
            source_text = Column(Text, nullable=False)
            target_text = Column(Text, nullable=False)
            source_language = Column(String(10), nullable=False, index=True)
            target_language = Column(String(10), nullable=False, index=True)
            api_provider = Column(String(50))
            confidence_score = Column(DECIMAL(3, 2))
            hit_count = Column(Integer, default=0, nullable=False)
            created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
            last_accessed = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
            expires_at = Column(DateTime(timezone=True), index=True)
        
        # 系统配置表
        class SystemConfiguration(Base):
            __tablename__ = "system_configurations"
            
            id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
            config_key = Column(String(100), unique=True, nullable=False, index=True)
            config_value = Column(JSONB, nullable=False)
            description = Column(Text)
            is_encrypted = Column(Boolean, default=False, nullable=False)
            created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
            updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
        
        # 场景配置表
        class SceneConfiguration(Base):
            __tablename__ = "scene_configurations"
            
            id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
            scene_type = Column(String(50), nullable=False, index=True)
            configuration = Column(JSONB, nullable=False)
            is_default = Column(Boolean, default=False, nullable=False)
            created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
            created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
            updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
        
        # 场景分析历史表
        class SceneAnalysisHistory(Base):
            __tablename__ = "scene_analysis_history"
            
            id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
            session_id = Column(UUID(as_uuid=True), ForeignKey("user_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
            scene_type = Column(String(50), index=True)
            confidence_score = Column(DECIMAL(3, 2))
            audio_features = Column(JSONB)
            content_features = Column(JSONB)
            analysis_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
        
        # API配置表
        class APIConfiguration(Base):
            __tablename__ = "api_configurations"
            
            id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
            provider_name = Column(String(50), nullable=False, index=True)
            service_type = Column(String(20), nullable=False, index=True)
            endpoint_url = Column(String(255), nullable=False)
            api_key_encrypted = Column(Text)
            model_name = Column(String(100))
            supported_languages = Column(JSONB)
            rate_limits = Column(JSONB)
            cost_per_request = Column(DECIMAL(10, 6))
            quality_score = Column(DECIMAL(3, 2))
            is_active = Column(Boolean, default=True, nullable=False)
            priority = Column(Integer, default=5, nullable=False)
            created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
            updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
        
        # API性能日志表
        class APIPerformanceLog(Base):
            __tablename__ = "api_performance_logs"
            
            id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
            api_provider = Column(String(50), nullable=False, index=True)
            service_type = Column(String(20), nullable=False, index=True)
            request_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
            request_id = Column(String(255), index=True)
            response_time_ms = Column(Integer)
            success = Column(Boolean, nullable=False, index=True)
            error_message = Column(Text)
            input_size = Column(Integer)
            output_size = Column(Integer)
            cost = Column(DECIMAL(10, 6))
        
        # 系统指标表
        class SystemMetric(Base):
            __tablename__ = "system_metrics"
            
            id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
            metric_name = Column(String(100), nullable=False, index=True)
            metric_value = Column(DECIMAL(15, 6))
            metric_unit = Column(String(20))
            labels = Column(JSONB)
            timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
        
        # 审计日志表
        class AuditLog(Base):
            __tablename__ = "audit_logs"
            
            id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
            user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
            action = Column(String(50), nullable=False, index=True)
            resource_type = Column(String(50), index=True)
            resource_id = Column(String(255), index=True)
            old_values = Column(JSONB)
            new_values = Column(JSONB)
            ip_address = Column(INET)
            user_agent = Column(Text)
            created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
        
        # 创建所有表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ 数据库表创建成功")
        
        # 插入默认数据
        print("📝 插入默认配置...")
        
        async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
            # 系统配置
            configs = [
                SystemConfiguration(
                    config_key="max_session_duration",
                    config_value=7200,
                    description="最大会话持续时间（秒）"
                ),
                SystemConfiguration(
                    config_key="cache_ttl_default",
                    config_value=3600,
                    description="默认缓存过期时间（秒）"
                ),
                SystemConfiguration(
                    config_key="max_translation_length",
                    config_value=5000,
                    description="单次翻译最大字符数"
                ),
                SystemConfiguration(
                    config_key="supported_audio_formats",
                    config_value=["wav", "mp3", "pcm", "flac"],
                    description="支持的音频格式"
                ),
                SystemConfiguration(
                    config_key="default_translation_engine",
                    config_value="alibaba_cloud",
                    description="默认翻译引擎"
                )
            ]
            
            for config in configs:
                session.add(config)
            
            # 场景配置
            scenes = [
                SceneConfiguration(
                    scene_type="business_meeting",
                    configuration={
                        "translation_style": "formal",
                        "terminology_preference": "business", 
                        "response_speed": "balanced",
                        "context_window": 20
                    },
                    is_default=True
                ),
                SceneConfiguration(
                    scene_type="casual_conversation",
                    configuration={
                        "translation_style": "casual",
                        "terminology_preference": "colloquial",
                        "response_speed": "fast",
                        "context_window": 10
                    },
                    is_default=True
                ),
                SceneConfiguration(
                    scene_type="technical_presentation",
                    configuration={
                        "translation_style": "precise",
                        "terminology_preference": "technical",
                        "response_speed": "accuracy_first",
                        "context_window": 30
                    },
                    is_default=True
                ),
                SceneConfiguration(
                    scene_type="academic_lecture",
                    configuration={
                        "translation_style": "formal",
                        "terminology_preference": "academic",
                        "response_speed": "accuracy_first",
                        "context_window": 25
                    },
                    is_default=True
                )
            ]
            
            for scene in scenes:
                session.add(scene)
            
            # API配置
            apis = [
                APIConfiguration(
                    provider_name="alibaba_cloud",
                    service_type="translation",
                    endpoint_url="https://dashscope.aliyuncs.com",
                    model_name="qwen-translate",
                    supported_languages=["zh", "en", "ja", "ko", "fr", "de", "es", "ru", "ar", "pt"],
                    is_active=True,
                    priority=1,
                    quality_score=0.9
                ),
                APIConfiguration(
                    provider_name="alibaba_cloud",
                    service_type="asr",
                    endpoint_url="https://dashscope.aliyuncs.com",
                    model_name="gummy-realtime-v1",
                    supported_languages=["zh", "en", "ja", "ko"],
                    is_active=True,
                    priority=1,
                    quality_score=0.85
                ),
                APIConfiguration(
                    provider_name="siliconflow",
                    service_type="tts",
                    endpoint_url="https://api.siliconflow.cn/v1/audio/speech",
                    model_name="CosyVoice2-0.5B",
                    supported_languages=["zh", "en"],
                    is_active=True,
                    priority=1,
                    quality_score=0.88
                )
            ]
            
            for api in apis:
                session.add(api)
            
            await session.commit()
        
        print("✅ 默认配置插入成功")
        
        # 验证创建结果
        print("🔍 验证数据库...")
        async with async_sessionmaker(engine, class_=AsyncSession)() as session:
            # 统计数据
            result = await session.execute(sqlalchemy.text("SELECT COUNT(*) FROM system_configurations"))
            config_count = result.scalar()
            
            result = await session.execute(sqlalchemy.text("SELECT COUNT(*) FROM scene_configurations"))
            scene_count = result.scalar()
            
            result = await session.execute(sqlalchemy.text("SELECT COUNT(*) FROM api_configurations"))
            api_count = result.scalar()
            
            print(f"📊 系统配置: {config_count} 条")
            print(f"📊 场景配置: {scene_count} 条")
            print(f"📊 API配置: {api_count} 条")
        
        await engine.dispose()
        
        print("\n" + "=" * 60)
        print("🎉 数据库初始化完成！")
        print("\n📋 已创建的表:")
        
        tables = [
            "users (用户表) - 存储用户信息",
            "user_sessions (用户会话表) - 记录用户会话",
            "translation_history (翻译历史表) - 保存翻译记录",
            "translation_cache (翻译缓存表) - 缓存翻译结果",
            "scene_configurations (场景配置表) - 场景设置",
            "scene_analysis_history (场景分析历史表) - 场景识别记录",
            "api_configurations (API配置表) - API提供商配置",
            "api_performance_logs (API性能日志表) - 性能监控",
            "system_configurations (系统配置表) - 系统设置",
            "system_metrics (系统指标表) - 监控指标",
            "audit_logs (审计日志表) - 操作日志"
        ]
        
        for i, table in enumerate(tables, 1):
            print(f"  {i:2d}. {table}")
        
        print(f"\n📊 初始数据统计:")
        print(f"  - 系统配置: {config_count} 条")
        print(f"  - 场景配置: {scene_count} 条")
        print(f"  - API配置: {api_count} 条")
        
        print("\n🔧 接下来你可以:")
        print("  1. 启动翻译服务: python services/translation/main.py")
        print("  2. 启动语音服务: python services/voice-interaction/main.py")
        print("  3. 启动场景识别服务: python services/scene-recognition/main.py")
        print("  4. 启动AI路由服务: python services/ai-router/main.py")
        print("  5. 测试API接口")
        
    except Exception as e:
        print(f"\n❌ 数据库初始化失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        print(f"详细错误:\n{traceback.format_exc()}")
        return False
    
    return True

def main():
    """主函数"""
    print("🚀 ZhiYUAI 2.0 数据库安装和初始化")
    print("=" * 60)
    
    # 设置环境变量
    os.environ["DATABASE_URL"] = "postgresql://postgres:123456@localhost:5432/gummy_translator"
    
    # 1. 安装依赖
    if not install_packages():
        print("❌ 依赖安装失败，无法继续")
        return
    
    print("\n" + "=" * 60)
    
    # 2. 初始化数据库
    try:
        success = asyncio.run(setup_database())
        if success:
            print("\n🎊 所有操作完成！数据库已就绪，可以开始使用服务了！")
        else:
            print("\n❌ 数据库初始化失败")
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断操作")
    except Exception as e:
        print(f"\n❌ 未预期的错误: {e}")

if __name__ == "__main__":
    main()