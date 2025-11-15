# 数据库集成使用指南
> 当前开源版本的 shared.database 模块以内存结构实现，便于演示与自动化测试；如果要对接真实 PostgreSQL，可按本文结构替换为数据库驱动。


## 概述

本文档介绍如何在 ZhiYUAI 2.0 项目中使用数据库集成功能。数据库集成模块提供了完整的数据访问层，包括 ORM 模型、仓储模式和高级集成功能。

## 架构概览

```
shared/database/
├── __init__.py          # 模块入口
├── base.py              # 数据库基础配置
├── session.py           # 会话管理
├── integration.py       # 高级集成功能
├── models/              # ORM 模型
│   ├── user.py         # 用户模型
│   ├── translation.py  # 翻译模型
│   ├── scene.py        # 场景模型
│   ├── api.py          # API 模型
│   ├── system.py       # 系统模型
│   └── audit.py        # 审计模型
└── repositories/        # 仓储模式实现
    ├── base.py         # 基础仓储
    ├── user.py         # 用户仓储
    ├── translation.py  # 翻译仓储
    ├── scene.py        # 场景仓储
    ├── api.py          # API 仓储
    ├── system.py       # 系统仓储
    └── audit.py        # 审计仓储
```

## 快速开始

### 1. 环境配置

在 `.env` 文件中配置数据库连接：

```bash
# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/gummy_translator
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30
DB_ECHO=false  # 是否显示 SQL 语句
```

### 2. 数据库初始化

使用数据库管理工具初始化数据库：

```bash
# 初始化数据库（创建表和默认数据）
python scripts/database/db_manager.py init

# 检查数据库状态
python scripts/database/db_manager.py check

# 查看统计信息
python scripts/database/db_manager.py stats
```

### 3. 在服务中使用数据库

#### 方式一：使用集成类（推荐）

```python
from shared.database.integration import TranslationServiceIntegration
import uuid

# 记录翻译历史
translation = await TranslationServiceIntegration.log_translation(
    user_id=uuid.uuid4(),
    session_id=uuid.uuid4(),
    source_text="Hello world",
    target_text="你好世界",
    source_language="en",
    target_language="zh",
    api_provider="alibaba_cloud",
    confidence_score=0.95,
    quality_score=0.90,
    processing_time=1500
)

# 获取缓存翻译
cached = await TranslationServiceIntegration.get_or_create_translation_cache(
    source_text="Hello world",
    source_language="en",
    target_language="zh"
)
```

#### 方式二：使用数据库服务

```python
from shared.database.integration import get_database_service

async def translation_endpoint():
    async with get_database_service() as db:
        # 查找用户
        user = await db.users.get_by_username("testuser")
        
        # 创建会话
        session = await db.user_sessions.create(
            user_id=user.id,
            session_id="session_123"
        )
        
        # 记录翻译
        translation = await db.translation_history.create(
            user_id=user.id,
            session_id=session.id,
            source_text="Hello",
            target_text="你好",
            source_language="en",
            target_language="zh",
            api_provider="test"
        )
        
        await db.commit()
```

#### 方式三：FastAPI 依赖注入

```python
from fastapi import Depends
from shared.database.integration import get_database_service, DatabaseService

@app.post("/translate")
async def translate(
    request: TranslationRequest,
    db: DatabaseService = Depends(get_database_service)
):
    # 使用数据库服务
    user = await db.users.get_by_id(request.user_id)
    
    # 执行翻译逻辑...
    
    # 记录翻译历史
    translation = await db.translation_history.create(
        user_id=user.id,
        session_id=request.session_id,
        source_text=request.text,
        target_text=result.text,
        source_language=request.source_language,
        target_language=request.target_language,
        api_provider=result.provider
    )
    
    await db.commit()
    return result
```

## 主要功能

### 1. 用户管理

```python
# 创建用户
user = await db.users.create(
    username="newuser",
    email="user@example.com",
    password_hash="hashed_password",
    profile={"name": "New User"},
    preferences={"language": "zh"}
)

# 根据用户名查找
user = await db.users.get_by_username("newuser")

# 获取付费用户
premium_users = await db.users.get_premium_users()

# 搜索用户
users = await db.users.search_users("search_term")
```

### 2. 会话管理

```python
# 创建会话
session = await db.user_sessions.create(
    user_id=user.id,
    session_id="unique_session_id",
    scene_type="business_meeting"
)

# 获取活跃会话
active_sessions = await db.user_sessions.get_active_sessions(user.id)

# 结束会话
await db.user_sessions.end_session("session_id")

# 更新会话指标
await db.user_sessions.update_session_metrics(
    session_id="session_id",
    translations_count=1,
    audio_duration=30
)
```

### 3. 翻译历史

```python
# 获取用户翻译历史
translations = await db.translation_history.get_user_translations(
    user_id=user.id,
    offset=0,
    limit=50
)

# 根据语言对查找
translations = await db.translation_history.get_by_language_pair("en", "zh")

# 全文搜索
results = await db.translation_history.search_translations("搜索关键词")

# 获取统计信息
stats = await db.translation_history.get_translation_statistics(user.id)
```

### 4. 翻译缓存

```python
# 获取缓存翻译
cached = await db.translation_cache.get_cached_translation(
    "Hello", "en", "zh"
)

# 缓存翻译结果
cache_entry = await db.translation_cache.cache_translation(
    source_text="Hello",
    target_text="你好",
    source_lang="en",
    target_lang="zh",
    api_provider="alibaba",
    confidence_score=0.95
)

# 清理过期缓存
deleted_count = await db.translation_cache.cleanup_expired_cache()
```

### 5. 场景配置

```python
# 获取场景配置
config = await SceneServiceIntegration.get_scene_configuration(
    scene_type="business_meeting",
    user_id=user.id  # 可选，获取用户自定义配置
)

# 记录场景分析
analysis = await SceneServiceIntegration.log_scene_analysis(
    session_id=session.id,
    scene_type="business_meeting",
    confidence_score=0.85,
    audio_features={"noise_level": 0.1},
    content_features={"formality": 0.8}
)
```

### 6. 系统配置和指标

```python
# 获取系统配置
max_length = await SystemIntegration.get_system_config(
    "max_translation_length", 5000
)

# 设置系统配置
await SystemIntegration.set_system_config(
    "feature_enabled", True, "新功能开关"
)

# 记录系统指标
await SystemIntegration.record_metric(
    name="translation_requests_total",
    value=1,
    labels={"service": "translation", "status": "success"}
)

# 记录用户操作
await SystemIntegration.log_user_action(
    action="login",
    user_id=user.id,
    ip_address="192.168.1.1"
)
```

## 事务管理

### 简单事务

```python
from shared.database.session import get_session

async with get_session() as session:
    # 所有操作在同一个事务中
    user = await db.users.create(...)
    session_obj = await db.user_sessions.create(...)
    # 事务自动提交或回滚
```

### 复杂事务

```python
from shared.database.session import get_transaction

async with get_transaction() as session:
    # 显式事务控制
    try:
        # 执行多个操作
        result1 = await operation1(session)
        result2 = await operation2(session)
        # 事务在 with 块结束时自动提交
    except Exception:
        # 发生异常时自动回滚
        raise
```

### 保存点（嵌套事务）

```python
from shared.database.session import DatabaseSession, TransactionManager

async with DatabaseSession() as session:
    tx_manager = TransactionManager(session)
    
    await tx_manager.begin()
    
    try:
        # 创建保存点
        sp1 = await tx_manager.savepoint("sp1")
        
        # 执行操作
        await operation1(session)
        
        try:
            sp2 = await tx_manager.savepoint("sp2")
            await risky_operation(session)
            await tx_manager.release_savepoint("sp2")
        except Exception:
            # 只回滚到 sp2
            await tx_manager.rollback_to_savepoint("sp2")
        
        await tx_manager.commit()
    except Exception:
        await tx_manager.rollback()
```

## 批量操作

```python
# 批量创建用户
users_data = [
    {"username": f"user_{i}", "email": f"user_{i}@example.com", "password_hash": "hash"}
    for i in range(100)
]
users = await db.users.bulk_create(users_data)

# 批量更新
updates = [
    {"id": user.id, "is_active": True}
    for user in users
]
updated_count = await db.users.bulk_update(updates)

# 批量删除
user_ids = [user.id for user in users[:10]]
deleted_count = await db.users.bulk_delete(user_ids)
```

## 性能优化

### 1. 查询优化

```python
# 预加载关联数据
user_with_sessions = await db.users.get_with_relations(
    user_id, relations=["sessions", "translation_history"]
)

# 分页查询
users = await db.users.get_all(offset=0, limit=50, order_by="created_at")

# 索引字段查询
user = await db.users.get_by_field("email", "user@example.com")
```

### 2. 缓存策略

```python
# 缓存翻译结果
cache_entry = await db.translation_cache.cache_translation(
    source_text="常用短语",
    target_text="common phrase",
    source_lang="zh",
    target_lang="en",
    api_provider="provider",
    ttl_seconds=7200  # 2小时过期
)

# 缓存优化
await db.translation_cache.optimize_cache(max_entries=10000)
```

### 3. 连接池配置

```python
# 在配置文件中调整
DATABASE_POOL_SIZE=20        # 连接池大小
DATABASE_MAX_OVERFLOW=40     # 最大溢出连接
DATABASE_POOL_TIMEOUT=60     # 连接超时时间
```

## 数据库管理

### 常用管理命令

```bash
# 初始化数据库
python scripts/database/db_manager.py init

# 检查数据库状态
python scripts/database/db_manager.py check

# 查看统计信息
python scripts/database/db_manager.py stats

# 清理过期数据（预演）
python scripts/database/db_manager.py cleanup --days 30 --dry-run

# 实际清理过期数据
python scripts/database/db_manager.py cleanup --days 30

# 重置数据库（危险操作）
python scripts/database/db_manager.py reset
```

### 监控和维护

```python
# 数据库健康检查
from shared.database.base import DatabaseHealthCheck

is_healthy = await DatabaseHealthCheck.check_connection()
conn_info = await DatabaseHealthCheck.get_connection_info()

# 获取缓存统计
cache_stats = await db.translation_cache.get_cache_statistics()

# 获取翻译统计
translation_stats = await db.translation_history.get_translation_statistics()

# 获取语言对使用统计
lang_stats = await db.translation_history.get_language_pair_stats()
```

## 测试

运行数据库集成测试：

```bash
# 运行所有数据库测试
pytest tests/unit/test_database_integration.py -v

# 运行特定测试类
pytest tests/unit/test_database_integration.py::TestModels -v

# 运行性能测试
pytest tests/unit/test_database_integration.py::TestPerformance -v
```

## 最佳实践

### 1. 错误处理

```python
try:
    async with get_session() as session:
        # 数据库操作
        result = await operation(session)
        return result
except Exception as e:
    logger.error("数据库操作失败", error=str(e))
    # 处理错误
    raise
```

### 2. 日志记录

```python
from shared.common import get_logger

logger = get_logger("service_name")

# 记录关键操作
logger.info("用户登录", user_id=user.id, ip=request.client.host)

# 记录性能指标
start_time = time.time()
result = await db_operation()
duration = time.time() - start_time
logger.debug("数据库操作完成", duration_ms=duration * 1000)
```

### 3. 安全性

```python
# 避免 SQL 注入（使用参数化查询）
users = await db.users.search_users(search_term)  # 安全

# 敏感数据加密
user = await db.users.create(
    username=username,
    password_hash=hash_password(password),  # 密码哈希
    profile=encrypt_sensitive_data(profile)  # 敏感信息加密
)

# 审计日志
await SystemIntegration.log_user_action(
    action="sensitive_operation",
    user_id=user.id,
    resource_id=resource.id,
    ip_address=request.client.host
)
```

## 故障排除

### 常见问题

1. **连接超时**
   - 检查数据库配置
   - 调整连接池参数
   - 检查网络连接

2. **性能问题**
   - 添加适当索引
   - 优化查询语句
   - 使用分页查询

3. **事务死锁**
   - 保持事务简短
   - 按固定顺序访问资源
   - 使用适当的隔离级别

4. **内存泄漏**
   - 确保正确关闭会话
   - 避免长时间持有连接
   - 定期清理过期数据

### 调试技巧

```python
# 启用 SQL 日志
# 在配置中设置 DB_ECHO=true

# 使用事务日志
async with get_session() as session:
    logger.debug("开始数据库事务")
    try:
        result = await operation(session)
        logger.debug("事务成功提交")
        return result
    except Exception as e:
        logger.error("事务失败回滚", error=str(e))
        raise
```

## 扩展和自定义

### 添加新模型

1. 在 `shared/database/models/` 中创建新模型文件
2. 在 `shared/database/repositories/` 中创建对应仓储
3. 在 `shared/database/integration.py` 中添加集成方法
4. 更新 `__init__.py` 导出列表

### 自定义仓储方法

```python
class CustomUserRepository(UserRepository):
    async def get_users_by_custom_criteria(self, criteria):
        # 自定义查询逻辑
        stmt = select(User).where(...)
        result = await self.session.execute(stmt)
        return result.scalars().all()
```

这个数据库集成系统为 ZhiYUAI 2.0 提供了强大而灵活的数据访问层，支持复杂的业务逻辑和高性能要求。