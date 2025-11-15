-- ZhiYUAI Database Initialization Script
-- 创建数据库和基础表结构

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============ 用户相关表 ============

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    profile JSONB DEFAULT '{}',
    preferences JSONB DEFAULT '{}',
    subscription_plan VARCHAR(20) DEFAULT 'free',
    last_login TIMESTAMP WITH TIME ZONE
);

-- 用户会话表
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP WITH TIME ZONE,
    duration INTEGER, -- 秒
    scene_type VARCHAR(50),
    language_pairs JSONB,
    quality_rating DECIMAL(3,2),
    total_translations INTEGER DEFAULT 0,
    total_audio_duration INTEGER DEFAULT 0 -- 秒
);

-- ============ 翻译相关表 ============

-- 翻译历史表
CREATE TABLE IF NOT EXISTS translation_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES user_sessions(id) ON DELETE CASCADE,
    source_text TEXT NOT NULL,
    target_text TEXT NOT NULL,
    source_language VARCHAR(10) NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    confidence_score DECIMAL(3,2),
    quality_score DECIMAL(3,2),
    api_provider VARCHAR(50),
    scene_context VARCHAR(50),
    processing_time INTEGER, -- 毫秒
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 全文搜索索引
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', source_text || ' ' || target_text)
    ) STORED
);

-- 翻译缓存表
CREATE TABLE IF NOT EXISTS translation_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA256哈希
    source_text TEXT NOT NULL,
    target_text TEXT NOT NULL,
    source_language VARCHAR(10) NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    api_provider VARCHAR(50),
    confidence_score DECIMAL(3,2),
    hit_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE
);

-- ============ AI服务相关表 ============

-- API配置表
CREATE TABLE IF NOT EXISTS api_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider_name VARCHAR(50) NOT NULL,
    service_type VARCHAR(20) NOT NULL, -- asr, translation, tts
    endpoint_url VARCHAR(255) NOT NULL,
    api_key_encrypted TEXT,
    model_name VARCHAR(100),
    supported_languages JSONB,
    rate_limits JSONB,
    cost_per_request DECIMAL(10,6),
    quality_score DECIMAL(3,2),
    is_active BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- API性能监控表
CREATE TABLE IF NOT EXISTS api_performance_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    api_provider VARCHAR(50) NOT NULL,
    service_type VARCHAR(20) NOT NULL,
    request_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    response_time_ms INTEGER,
    success BOOLEAN,
    error_message TEXT,
    input_size INTEGER,
    output_size INTEGER,
    cost DECIMAL(10,6),
    request_id VARCHAR(255)
);

-- ============ 场景识别相关表 ============

-- 场景配置表
CREATE TABLE IF NOT EXISTS scene_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scene_type VARCHAR(50) NOT NULL,
    configuration JSONB NOT NULL,
    is_default BOOLEAN DEFAULT false,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 场景分析历史表
CREATE TABLE IF NOT EXISTS scene_analysis_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES user_sessions(id) ON DELETE CASCADE,
    scene_type VARCHAR(50),
    confidence_score DECIMAL(3,2),
    audio_features JSONB,
    content_features JSONB,
    analysis_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============ 系统配置和监控表 ============

-- 系统配置表
CREATE TABLE IF NOT EXISTS system_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value JSONB NOT NULL,
    description TEXT,
    is_encrypted BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 系统指标表
CREATE TABLE IF NOT EXISTS system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,6),
    metric_unit VARCHAR(20),
    labels JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 审计日志表
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============ 索引创建 ============

-- 用户表索引
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- 会话表索引
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON user_sessions(start_time);

-- 翻译历史索引
CREATE INDEX IF NOT EXISTS idx_translation_user_id ON translation_history(user_id);
CREATE INDEX IF NOT EXISTS idx_translation_session_id ON translation_history(session_id);
CREATE INDEX IF NOT EXISTS idx_translation_created_at ON translation_history(created_at);
CREATE INDEX IF NOT EXISTS idx_translation_languages ON translation_history(source_language, target_language);
CREATE INDEX IF NOT EXISTS idx_translation_search ON translation_history USING gin(search_vector);

-- 翻译缓存索引
CREATE INDEX IF NOT EXISTS idx_cache_hash ON translation_cache(content_hash);
CREATE INDEX IF NOT EXISTS idx_cache_languages ON translation_cache(source_language, target_language);
CREATE INDEX IF NOT EXISTS idx_cache_accessed ON translation_cache(last_accessed);

-- API性能监控索引
CREATE INDEX IF NOT EXISTS idx_api_perf_provider ON api_performance_logs(api_provider);
CREATE INDEX IF NOT EXISTS idx_api_perf_time ON api_performance_logs(request_time);
CREATE INDEX IF NOT EXISTS idx_api_perf_success ON api_performance_logs(success);

-- 系统指标索引
CREATE INDEX IF NOT EXISTS idx_metrics_name_time ON system_metrics(metric_name, timestamp);

-- ============ 触发器函数 ============

-- 更新时间戳触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为需要的表创建更新时间戳触发器
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_api_configurations_updated_at 
    BEFORE UPDATE ON api_configurations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scene_configurations_updated_at 
    BEFORE UPDATE ON scene_configurations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_configurations_updated_at 
    BEFORE UPDATE ON system_configurations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============ 初始数据插入 ============

-- 插入默认API配置
INSERT INTO api_configurations (provider_name, service_type, endpoint_url, model_name, supported_languages, is_active, priority)
VALUES 
    ('alibaba_cloud', 'asr', 'https://dashscope.aliyuncs.com', 'gummy-realtime-v1', '["zh", "en", "ja", "ko"]'::jsonb, true, 1),
    ('alibaba_cloud', 'translation', 'https://dashscope.aliyuncs.com', 'qwen-translate', '["zh", "en", "ja", "ko", "fr", "de", "es", "ru", "ar", "pt"]'::jsonb, true, 1),
    ('siliconflow', 'tts', 'https://api.siliconflow.cn/v1/audio/speech', 'CosyVoice2-0.5B', '["zh", "en"]'::jsonb, true, 1)
ON CONFLICT DO NOTHING;

-- 插入默认场景配置
INSERT INTO scene_configurations (scene_type, configuration, is_default)
VALUES 
    ('business_meeting', '{"translation_style": "formal", "terminology_preference": "business", "response_speed": "balanced", "context_window": 20}'::jsonb, true),
    ('casual_conversation', '{"translation_style": "casual", "terminology_preference": "colloquial", "response_speed": "fast", "context_window": 10}'::jsonb, true),
    ('technical_presentation', '{"translation_style": "precise", "terminology_preference": "technical", "response_speed": "accuracy_first", "context_window": 30}'::jsonb, true)
ON CONFLICT DO NOTHING;

-- 插入系统默认配置
INSERT INTO system_configurations (config_key, config_value, description)
VALUES 
    ('max_session_duration', '7200', '最大会话持续时间（秒）'),
    ('cache_ttl_default', '3600', '默认缓存过期时间（秒）'),
    ('max_translation_length', '5000', '单次翻译最大字符数'),
    ('supported_audio_formats', '["wav", "mp3", "pcm", "flac"]', '支持的音频格式')
ON CONFLICT DO NOTHING;

-- ============ 数据库优化设置 ============

-- 设置一些性能优化参数
-- 这些可以根据实际部署环境调整

-- 创建统计信息收集作业（可选）
-- ANALYZE;

COMMIT;