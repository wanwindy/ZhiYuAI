# ZhiYUAI Mobile (Flutter)

Flutter 客户端，覆盖文本翻译与语音同传（ASR → Translate → TTS）闭环，基于 PRD 开发。

## 运行前置
- 安装 Flutter SDK (3.22+)
- 安装 Android Studio / Xcode（对应平台工具链与模拟器）

## 初始化与运行
```bash
cd mobile-app/flutter
# 若未存在平台目录（android/ios），先初始化：
flutter create .

# 拉取依赖
flutter pub get

# 运行（根据本地后端端口调整 dart-define）
flutter run \
  --dart-define=TRANSLATION_BASE_URL=http://localhost:8002 \
  --dart-define=VOICE_BASE_URL=http://localhost:8000 \
  --dart-define=AI_ROUTER_BASE_URL=http://localhost:8003
```

> 提示：默认直连各服务端口。接入 API 网关后，仅需调整 `--dart-define`。

## 功能概览
- 文本翻译：输入 → 翻译结果（质量/引擎标签），支持语言切换
- 翻译导出：单条翻译支持复制译文/复制详情；导出 TXT/CSV 并系统分享
- 语音同传：录音 → 识别（ASR）→ 翻译 → 合成播放（TTS）
- 历史：按会话获取翻译历史（来自 Translation Service）
- 设置：语言/引擎偏好与 Base URL 切换（持久化）

## 目录结构
```
lib/
  core/            # 环境、网络、存储、音频等基础设施
  features/
    translate/     # 文本翻译模块（数据/UI/Provider）
    voice/         # 语音同传模块（数据/UI/Provider）
    history/       # 历史列表
    settings/      # 设置页
  routing/         # 路由与底部导航
  app.dart         # 根应用
  main.dart        # 入口
```

## 注意
- 录音采用 16k 采样 WAV/PCM，上传 Base64 到 `/voice/recognize`
- TTS 优先使用 `audio_url`，若返回 `audio_data` 则 Base64 解码播放
- 会话通过 `/session/create` 获取 `session_id` 后贯通各接口

### 平台权限
- iOS: 在 `ios/Runner/Info.plist` 添加
  ```xml
  <key>NSMicrophoneUsageDescription</key>
  <string>需要麦克风用于语音识别</string>
  ```
- Android: 在 `android/app/src/main/AndroidManifest.xml` 确认包含
  ```xml
  <uses-permission android:name="android.permission.RECORD_AUDIO"/>
  <uses-permission android:name="android.permission.INTERNET"/>
  <!-- 后台播放通知建议权限（Android 13+ 通知权限） -->
  <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
  <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK"/>
  ```

如需新增接口或调试，请参考：
- services/voice-interaction/main.py
- services/translation/main.py
- services/ai-router/main.py
- shared/common/config.py

## Windows/Android 构建常见问题（JDK/Gradle）

若在 `flutter run`/`assembleDebug` 期间出现如下错误：

```
Exception in thread "main" java.lang.InternalError: Error loading java.security file
  at java.base/java.security.Security.initialize(...)
  ...
  at org.gradle.wrapper.PathAssembler.getHash(PathAssembler.java:65)
```

通常是 Gradle 调用了系统 PATH 中的 Java（如 GraalVM 或损坏的 JRE），无法正确加载 `java.security`。建议按以下步骤修复：

- 优先使用 Android Studio 自带 JDK（JBR，JDK 17）：
  - 执行：
    - `flutter config --jdk-dir "C:\\Program Files\\Android\\Android Studio\\jbr"`
  - 或在用户级 Gradle 配置中指定 JDK：
    - 在 `%USERPROFILE%\.gradle\gradle.properties` 写入：
      - `org.gradle.java.home=C:\\Program Files\\Android\\Android Studio\\jbr`

- 清理并重试：
  - `flutter clean && flutter pub get && flutter run`

- 若仍失败，检查环境变量与 Java 顺序：
  - 运行 `where java`，确认首个命令来自 `Android Studio\jbr\bin\java.exe`
  - 避免 `...\jre\bin` 及 GraalVM 在 PATH 前列，必要时：
    - `setx JAVA_HOME "C:\\Program Files\\Android\\Android Studio\\jbr"`
    - `setx PATH "%JAVA_HOME%\\bin;%PATH%"`

上述方式不会修改仓库文件路径，适合团队协作与跨机环境。
