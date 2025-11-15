
// ZhiYUAI Web 控制台交互脚本

class AudioResampler {
    constructor(sourceSampleRate, targetSampleRate = 16000) {
        this.sourceSampleRate = sourceSampleRate;
        this.targetSampleRate = targetSampleRate;
        this.ratio = sourceSampleRate / targetSampleRate;
        this._buffer = new Float32Array(0);
    }

    process(chunk) {
        if (!chunk || chunk.length === 0) {
            return new Int16Array(0);
        }

        const combined = new Float32Array(this._buffer.length + chunk.length);
        combined.set(this._buffer);
        combined.set(chunk, this._buffer.length);

        if (this.sourceSampleRate === this.targetSampleRate) {
            this._buffer = new Float32Array(0);
            return this._floatArrayToInt16(combined);
        }

        const outputLength = Math.max(0, Math.floor((combined.length - 1) / this.ratio));
        if (outputLength === 0) {
            this._buffer = combined;
            return new Int16Array(0);
        }

        const output = new Int16Array(outputLength);
        for (let i = 0; i < outputLength; i++) {
            const position = i * this.ratio;
            const index = Math.floor(position);
            const nextIndex = Math.min(combined.length - 1, index + 1);
            const fraction = position - index;
            const sample = combined[index] * (1 - fraction) + combined[nextIndex] * fraction;
            output[i] = this._floatTo16(sample);
        }

        const consumed = Math.floor(outputLength * this.ratio);
        const remaining = combined.length - consumed;
        if (remaining > 0) {
            this._buffer = combined.slice(consumed);
        } else {
            this._buffer = new Float32Array(0);
        }
        return output;
    }

    flush() {
        if (this._buffer.length === 0) {
            return new Int16Array(0);
        }
        const tail = this.process(new Float32Array(0));
        this._buffer = new Float32Array(0);
        return tail;
    }

    _floatArrayToInt16(floatArray) {
        const output = new Int16Array(floatArray.length);
        for (let i = 0; i < floatArray.length; i++) {
            output[i] = this._floatTo16(floatArray[i]);
        }
        return output;
    }

    _floatTo16(value) {
        const clamped = Math.max(-1, Math.min(1, value));
        return clamped < 0 ? Math.round(clamped * 0x8000) : Math.round(clamped * 0x7fff);
    }
}
class GummyTranslator {
    constructor() {
        this.protocol = window.location.protocol.startsWith('https') ? 'https:' : 'http:';
        this.hostname = window.location.hostname || 'localhost';
        this.serviceOverrides = this.normalizeServiceOverrides(window.GUMMY_SERVICE_OVERRIDES);
        this.services = {
            translation: { port: 8002, label: '翻译服务' },
            aiRouter:    { port: 8001, label: 'AI 路由服务' },
            scene:       { port: 8003, label: '场景识别服务' },
            voice:       { port: 8004, label: '语音交互服务' },
        };

        this.isRecording = false;
        this.voiceSocket = null;
        this.audioStream = null;
        this.audioSourceNode = null;
        this.audioProcessorNode = null;
        this.audioOutputNode = null;
        this.audioResampler = null;
        this.streamedAudioBytes = 0;
        this.maxStreamingBytes = 4.5 * 1024 * 1024; // Keep client usage slightly below server limit
        this.streamLimitReached = false;
        this.cameraStream = null;
        this.activeAudio = null;
        this.audioContext = null;
        this.toastTimer = null;
        this.sceneHistory = [];
        this.voiceTranslationMap = new Map();
        this.voiceTranscriptText = '';
        this.voiceSocketTargetLanguage = null;
        this.voiceSessionCompleted = false;
        // Scene live (video + voice)
        this.sceneLiveSocket = null;
        this.sceneLiveIsRecording = false;
        this.sceneLiveAudioStream = null;
        this.sceneLiveSourceNode = null;
        this.sceneLiveProcessorNode = null;
        this.sceneLiveResampler = null;
        this.sceneLiveStreamedAudioBytes = 0;
        this.sceneLiveMaxBytes = 4.5 * 1024 * 1024;
        this.sceneLiveFrameTimer = null;
        this.sceneLiveFrameIntervalMs = 1500;
        this.sceneLiveMuteGainNode = null;
        this.sceneLivePendingInt16 = new Int16Array(0);
        this.sceneLiveChunkSamples = 640;

        this.voicePendingInt16 = new Int16Array(0);
        this.voiceChunkSamples = 640;

        this.audioWorkletModuleLoaded = false;
        this.audioWorkletModuleLoading = null;

        this.dom = {};
        this.init();
    }

    init() {
        this.cacheDom();
        this.bindEvents();
        this.resetSceneDialogue(true);
        this.checkServices();
        setInterval(() => this.checkServices(), 15000);
    }

    cacheDom() {
        this.dom = {
            status: document.getElementById('status'),
            sourceText: document.getElementById('sourceText'),
            translatedText: document.getElementById('translatedText'),
            sourceLanguage: document.getElementById('sourceLanguage'),
            targetLanguage: document.getElementById('targetLanguage'),
            translationInfo: document.getElementById('translationInfo'),
            translateBtn: document.getElementById('translateBtn'),
            clearTextBtn: document.getElementById('clearTextBtn'),
            copyBtn: document.getElementById('copyBtn'),
            speakBtn: document.getElementById('speakBtn'),
            recordBtn: document.getElementById('recordBtn'),
            recordStatus: document.getElementById('recordStatus'),
            waveform: document.getElementById('waveform'),
            voiceResult: document.getElementById('voiceResult'),
            startCameraBtn: document.getElementById('startCameraBtn'),
            stopCameraBtn: document.getElementById('stopCameraBtn'),
            captureBtn: document.getElementById('captureBtn'),
            cameraPreview: document.getElementById('cameraPreview'),
            cameraPlaceholder: document.getElementById('cameraPlaceholder'),
            cameraResult: document.getElementById('cameraResult'),
            sceneText: document.getElementById('sceneText'),
            recognizeBtn: document.getElementById('recognizeBtn'),
            sceneResult: document.getElementById('sceneResult'),
            sceneChat: document.getElementById('sceneChat'),
            sceneChatInput: document.getElementById('sceneChatInput'),
            sceneSendBtn: document.getElementById('sceneSendBtn'),
            sceneResetBtn: document.getElementById('sceneResetBtn'),
            // Scene live UI
            sceneReplyLanguage: document.getElementById('sceneReplyLanguage'),
            sceneLiveStartBtn: document.getElementById('sceneLiveStartBtn'),
            sceneLiveStopBtn: document.getElementById('sceneLiveStopBtn'),
            sceneLiveTranscript: document.getElementById('sceneLiveTranscript'),
            sceneLiveAssistantText: document.getElementById('sceneLiveAssistantText'),
            toast: document.getElementById('toast'),
            toastIcon: document.getElementById('toastIcon'),
            toastMessage: document.getElementById('toastMessage'),
        };
    }

    bindEvents() {
        this.dom.translateBtn.addEventListener('click', () => this.translateText());
        this.dom.clearTextBtn.addEventListener('click', () => this.clearText());
        this.dom.copyBtn.addEventListener('click', () => this.copyTranslation());
        this.dom.speakBtn.addEventListener('click', () => this.speakText());
        this.dom.recordBtn.addEventListener('click', () => this.toggleRecording());
        this.dom.startCameraBtn.addEventListener('click', () => this.startCamera());
        this.dom.stopCameraBtn.addEventListener('click', () => this.stopCamera());
        this.dom.captureBtn.addEventListener('click', () => this.capturePhoto());
        this.dom.recognizeBtn.addEventListener('click', () => this.recognizeScene());
        this.dom.sceneSendBtn.addEventListener('click', () => this.sendSceneMessage());
        this.dom.sceneResetBtn.addEventListener('click', () => this.resetSceneDialogue());
        if (this.dom.sceneLiveStartBtn) {
            this.dom.sceneLiveStartBtn.addEventListener('click', () => this.startSceneLive());
        }
        if (this.dom.sceneLiveStopBtn) {
            this.dom.sceneLiveStopBtn.addEventListener('click', () => this.stopSceneLive());
        }
        this.dom.sceneChatInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                this.sendSceneMessage();
            }
        });
        this.dom.sourceText.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && event.ctrlKey) {
                event.preventDefault();
                this.translateText();
            }
        });
    }

    normalizeServiceOverrides(rawOverrides) {
        if (!rawOverrides || typeof rawOverrides !== 'object') {
            return {};
        }
        const normalized = {};
        for (const [key, value] of Object.entries(rawOverrides)) {
            if (!value) continue;
            if (typeof value === 'string') {
                const httpUrl = this.resolveUrl(value, this.protocol);
                normalized[key] = {
                    http: httpUrl,
                    ws: this.deriveWsUrl(httpUrl),
                };
                continue;
            }
            if (typeof value === 'object') {
                const httpCandidate = value.http || value.baseUrl || value.url;
                const wsCandidate = value.ws || value.wsBaseUrl || value.wsUrl;
                const httpUrl = httpCandidate ? this.resolveUrl(httpCandidate, this.protocol) : null;
                let wsUrl = wsCandidate
                    ? this.resolveUrl(wsCandidate, this.protocol === 'https:' ? 'wss:' : 'ws:')
                    : null;
                if (!wsUrl && httpUrl) {
                    wsUrl = this.deriveWsUrl(httpUrl);
                }
                normalized[key] = {
                    http: httpUrl,
                    ws: wsUrl,
                };
            }
        }
        return normalized;
    }

    resolveUrl(value, defaultProtocol) {
        if (!value) return null;
        const trimmed = typeof value === 'string' ? value.trim() : '';
        if (!trimmed) return null;
        if (/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(trimmed)) {
            return trimmed.replace(/\/+$/, '');
        }
        if (trimmed.startsWith('//')) {
            const protocol = defaultProtocol || this.protocol;
            return `${protocol}${trimmed}`.replace(/\/+$/, '');
        }
        try {
            const absolute = new URL(trimmed, window.location.origin);
            return absolute.href.replace(/\/+$/, '');
        } catch (_error) {
            return null;
        }
    }

    deriveWsUrl(httpUrl) {
        if (!httpUrl) return null;
        try {
            const url = new URL(httpUrl, window.location.origin);
            url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
            return url.href.replace(/\/+$/, '');
        } catch (_error) {
            return null;
        }
    }

    serviceHttpUrl(serviceKey) {
        const override = this.serviceOverrides?.[serviceKey]?.http;
        if (override) {
            return override;
        }
        const service = this.services[serviceKey];
        if (!service) {
            throw new Error(`未知服务: ${serviceKey}`);
        }
        return `${this.protocol}//${this.hostname}:${service.port}`;
    }

    serviceWsUrl(serviceKey) {
        const override = this.serviceOverrides?.[serviceKey];
        if (override?.ws) {
            return override.ws;
        }
        if (override?.http) {
            const derived = this.deriveWsUrl(override.http);
            if (derived) {
                return derived;
            }
        }
        const service = this.services[serviceKey];
        if (!service) {
            throw new Error(`未知服务: ${serviceKey}`);
        }
        const wsProtocol = this.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${wsProtocol}//${this.hostname}:${service.port}`;
    }

    // ===================== Realtime Scene Dialogue (Video + Voice) =====================

    async openSceneLiveSocket(replyLanguage) {
        return new Promise((resolve, reject) => {
            const baseUrl = this.serviceWsUrl('scene');
            const url = `${baseUrl}/dialogue/live?reply_language=${encodeURIComponent(
                replyLanguage || 'Chinese'
            )}`;
            const socket = new WebSocket(url);
            socket.binaryType = 'arraybuffer';
            const handleInitialError = (event) => {
                console.error('Scene live socket connection error:', event);
                socket.onopen = null;
                socket.onclose = null;
                socket.onerror = null;
                reject(new Error('实时场景对话服务连接失败'));
            };
            socket.onopen = () => {
                socket.onerror = (event) => this.handleSceneLiveError(event);
                socket.onclose = () => this.handleSceneLiveClose();
                socket.onmessage = (event) => this.handleSceneLiveMessage(event);
                this.sceneLiveSocket = socket;
                resolve();
            };
            socket.onerror = handleInitialError;
            socket.onclose = (event) => {
                if (socket.readyState !== WebSocket.OPEN && this.sceneLiveSocket !== socket) {
                    handleInitialError(event);
                }
            };
        });
    }

    async startSceneLive() {
        if (this.sceneLiveIsRecording) {
            return;
        }
        // Do not overlap with voice translation pipeline
        if (this.isRecording) {
            this.showToast('请先停止“实时语音翻译”，再开始场景对话', 'warning');
            return;
        }
        // Try to unlock audio playback under user gesture
        try { await this.unlockAudioPlayback(); } catch (_) {}
        const replyLanguage = (this.dom.sceneReplyLanguage && this.dom.sceneReplyLanguage.value) || 'Chinese';
        this.sceneLiveStreamedAudioBytes = 0;
        try {
            await this.openSceneLiveSocket(replyLanguage);
        } catch (error) {
            this.showToast(error.message || '无法连接场景对话服务', 'error');
            return;
        }
        // Setup audio capture
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: 16000,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });
            this.sceneLiveAudioStream = stream;
            await this.ensureAudioContext();
            await this.ensureAudioWorkletModule();
            this.sceneLiveSourceNode = this.audioContext.createMediaStreamSource(stream);
            const processor = new AudioWorkletNode(this.audioContext, 'pcm-frame-sender', {
                numberOfInputs: 1,
                numberOfOutputs: 1,
                channelCount: 1,
                outputChannelCount: [1],
            });
            this.sceneLiveProcessorNode = processor;
            const actualRate = this.audioContext.sampleRate || 48000;
            this.sceneLiveResampler = new AudioResampler(actualRate, 16000);
            const sceneRatio = this.sceneLiveResampler.ratio || 1;
            this.sceneLiveChunkSamples = Math.max(320, Math.round(4096 / Math.max(sceneRatio, 1)));
            this.sceneLivePendingInt16 = new Int16Array(0);
            processor.port.onmessage = ({ data }) => this.sceneLiveHandleAudioFrame(data);
            processor.port.onmessageerror = (event) => {
                console.error('Scene live worklet message error:', event);
            };
            this.sceneLiveSourceNode.connect(processor);
            // Mute local mic monitoring to avoid feedback
            const muteGain = this.audioContext.createGain();
            muteGain.gain.value = 0;
            this.sceneLiveMuteGainNode = muteGain;
            processor.connect(muteGain);
            muteGain.connect(this.audioContext.destination);
        } catch (error) {
            console.error('Scene live mic error:', error);
            const message = error && error.message ? error.message : '无法访问麦克风，请检查权限';
            this.showToast(message, 'error');
            this.stopSceneLive(true);
            return;
        }

        // Start frame timer if camera is on
        if (this.cameraStream && this.dom.cameraPreview && !this.sceneLiveFrameTimer) {
            this.sceneLiveFrameTimer = setInterval(() => this.sendSceneFrameFromPreview(), this.sceneLiveFrameIntervalMs);
        }

        this.sceneLiveIsRecording = true;
        if (this.dom.sceneLiveStartBtn && this.dom.sceneLiveStopBtn) {
            this.dom.sceneLiveStartBtn.classList.add('hidden');
            this.dom.sceneLiveStopBtn.classList.remove('hidden');
        }
        this.showToast('已开始实时场景对话', 'success');
    }

    async stopSceneLive(forceClose = false) {
        if (!this.sceneLiveIsRecording && !forceClose) {
            return;
        }
        // Flush remaining audio
        if (this.sceneLiveResampler) {
            const tail = this.sceneLiveResampler.flush();
            if (tail && tail.length) {
                this.appendSceneLiveSamples(tail);
            }
        }
        this.flushSceneLivePendingAudio(true);
        this.cleanupSceneLiveAudio();
        // Tell server to end this turn
        if (this.sceneLiveSocket && this.sceneLiveSocket.readyState === WebSocket.OPEN) {
            try {
                this.sceneLiveSocket.send(JSON.stringify({ type: 'stop' }));
            } catch (e) {
                // ignore
            }
        }
        // Stop sending camera frames for now
        if (this.sceneLiveFrameTimer) {
            clearInterval(this.sceneLiveFrameTimer);
            this.sceneLiveFrameTimer = null;
        }
        this.sceneLiveIsRecording = false;
        if (this.dom.sceneLiveStartBtn && this.dom.sceneLiveStopBtn) {
            this.dom.sceneLiveStartBtn.classList.remove('hidden');
            this.dom.sceneLiveStopBtn.classList.add('hidden');
        }
        if (forceClose) {
            this.closeSceneLiveSocket(true);
        }
        this.showToast('已结束本轮场景对话', 'info');
    }

    async unlockAudioPlayback() {
        try {
            await this.ensureAudioContext();
            const ctx = this.audioContext;
            const gain = ctx.createGain();
            gain.gain.value = 0.0; // silent prime
            const osc = ctx.createOscillator();
            osc.type = 'sine';
            osc.frequency.value = 440;
            osc.connect(gain);
            gain.connect(ctx.destination);
            const now = ctx.currentTime;
            osc.start(now);
            osc.stop(now + 0.02);
        } catch (_) {
            // ignore
        }
    }

    sendSceneFrameFromPreview() {
        if (!this.sceneLiveSocket || this.sceneLiveSocket.readyState !== WebSocket.OPEN) return;
        if (!this.cameraStream || !this.dom.cameraPreview) return;
        const video = this.dom.cameraPreview;
        if (!video.videoWidth || !video.videoHeight) return;
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.6);
        const base64 = dataUrl.split(',')[1] || '';
        try {
            this.sceneLiveSocket.send(JSON.stringify({ type: 'frame', image_base64: base64 }));
        } catch (err) {
            console.warn('Send scene frame failed:', err);
        }
    }

    sceneLiveHandleAudioFrame(frame) {
        if (!this.sceneLiveIsRecording || !this.sceneLiveSocket || this.sceneLiveSocket.readyState !== WebSocket.OPEN) {
            return;
        }
        if (!frame) return;
        const input = frame instanceof Float32Array ? frame : new Float32Array(frame);
        if (input.length === 0) return;
        const resampler = this.sceneLiveResampler;
        if (!resampler) return;
        const chunk = resampler.process(input);
        if (chunk && chunk.length) {
            this.appendSceneLiveSamples(chunk);
        }
    }

    sceneLiveSendAudioChunk(chunk) {
        if (!this.sceneLiveSocket || this.sceneLiveSocket.readyState !== WebSocket.OPEN) return;
        const payload = chunk.buffer.slice(chunk.byteOffset, chunk.byteOffset + chunk.byteLength);
        const next = this.sceneLiveStreamedAudioBytes + payload.byteLength;
        if (next > this.sceneLiveMaxBytes) {
            this.showToast('音频超过实时场景对话限制，自动结束', 'warning');
            this.stopSceneLive();
            return;
        }
        this.sceneLiveStreamedAudioBytes = next;
        try {
            this.sceneLiveSocket.send(payload);
        } catch (err) {
            console.warn('Scene live send audio failed:', err);
            this.stopSceneLive(true);
        }
    }

    appendSceneLiveSamples(samples) {
        if (!samples || !samples.length) {
            return;
        }
        this.sceneLivePendingInt16 = this.concatInt16Arrays(this.sceneLivePendingInt16, samples);
        this.flushSceneLivePendingAudio();
    }

    flushSceneLivePendingAudio(force = false) {
        const chunkSize = this.sceneLiveChunkSamples || 0;
        if (!chunkSize) {
            if (force && this.sceneLivePendingInt16.length > 0) {
                this.sceneLiveSendAudioChunk(this.sceneLivePendingInt16);
                this.sceneLivePendingInt16 = new Int16Array(0);
            }
            return;
        }
        while (this.sceneLivePendingInt16.length >= chunkSize) {
            const frame = this.sceneLivePendingInt16.slice(0, chunkSize);
            this.sceneLiveSendAudioChunk(frame);
            this.sceneLivePendingInt16 = this.sceneLivePendingInt16.slice(chunkSize);
        }
        if (force && this.sceneLivePendingInt16.length > 0) {
            this.sceneLiveSendAudioChunk(this.sceneLivePendingInt16);
            this.sceneLivePendingInt16 = new Int16Array(0);
        }
    }

    concatInt16Arrays(current, next) {
        const nextArray = next instanceof Int16Array ? next : new Int16Array(next || []);
        if (!current || current.length === 0) {
            return new Int16Array(nextArray);
        }
        if (!nextArray.length) {
            return current;
        }
        const merged = new Int16Array(current.length + nextArray.length);
        merged.set(current, 0);
        merged.set(nextArray, current.length);
        return merged;
    }

    cleanupSceneLiveAudio() {
        if (this.sceneLiveProcessorNode) {
            try {
                this.sceneLiveProcessorNode.disconnect();
            } catch (_) {}
            if (this.sceneLiveProcessorNode.port) {
                this.sceneLiveProcessorNode.port.onmessage = null;
                this.sceneLiveProcessorNode.port.onmessageerror = null;
                try {
                    this.sceneLiveProcessorNode.port.close();
                } catch (_) {}
            }
            this.sceneLiveProcessorNode = null;
        }
        if (this.sceneLiveMuteGainNode) {
            try {
                this.sceneLiveMuteGainNode.disconnect();
            } catch (_) {}
            this.sceneLiveMuteGainNode = null;
        }
        if (this.sceneLiveSourceNode) {
            try {
                this.sceneLiveSourceNode.disconnect();
            } catch (_) {}
            this.sceneLiveSourceNode = null;
        }
        if (this.sceneLiveAudioStream) {
            try {
                this.sceneLiveAudioStream.getTracks().forEach((t) => t.stop());
            } catch (_) {}
            this.sceneLiveAudioStream = null;
        }
        this.sceneLiveResampler = null;
        this.sceneLivePendingInt16 = new Int16Array(0);
    }

    closeSceneLiveSocket(force = false) {
        if (!this.sceneLiveSocket) return;
        const socket = this.sceneLiveSocket;
        this.sceneLiveSocket = null;
        try {
            if (force && socket.readyState === WebSocket.OPEN) {
                socket.close(1011, 'client-close');
            } else {
                socket.close();
            }
        } catch (err) {
            console.warn('Scene live close error:', err);
        }
    }

    handleSceneLiveMessage(event) {
        let payload;
        try {
            payload = JSON.parse(event.data);
        } catch (error) {
            console.warn('Invalid scene-live payload:', event.data);
            return;
        }
        switch (payload.type) {
            case 'ready':
                this.showToast('场景对话已就绪', 'info');
                break;
            case 'scene':
                this.dom.sceneResult.innerHTML = `
                    <div class="space-y-1">
                        <p>场景：<span class="font-medium">${payload.scenario_name || '未知'}</span>（置信度 ${(payload.confidence != null ? (payload.confidence * 100).toFixed(1) : '—')}%）</p>
                        <p class="text-gray-700">${payload.summary || ''}</p>
                        <p class="text-gray-600 text-xs">策略：${JSON.stringify(payload.recommended_settings || {})}</p>
                    </div>`;
                break;
            case 'transcript':
                if (this.dom.sceneLiveTranscript) this.dom.sceneLiveTranscript.textContent = payload.text || '';
                break;
            case 'assistant_text':
                if (this.dom.sceneLiveAssistantText) this.dom.sceneLiveAssistantText.textContent = payload.text || '';
                break;
            case 'assistant_audio':
                if (payload.audio_base64) {
                    this.playAudio(payload.audio_base64, payload.audio_format || 'wav');
                }
                break;
            case 'done':
                // For one-turn UX, close after done
                this.closeSceneLiveSocket();
                break;
            case 'error':
                this.showToast(payload.message || '场景对话出错', 'error');
                this.closeSceneLiveSocket(true);
                break;
            default:
                break;
        }
    }

    handleSceneLiveError(event) {
        console.error('Scene live socket error:', event);
        this.showToast('场景对话连接异常', 'error');
        this.closeSceneLiveSocket(true);
    }

    handleSceneLiveClose() {
        if (this.sceneLiveIsRecording) {
            this.sceneLiveIsRecording = false;
            this.cleanupSceneLiveAudio();
            if (this.dom.sceneLiveStartBtn && this.dom.sceneLiveStopBtn) {
                this.dom.sceneLiveStartBtn.classList.remove('hidden');
                this.dom.sceneLiveStopBtn.classList.add('hidden');
            }
        }
    }

    async checkServices() {
        const states = await Promise.all(
            Object.entries(this.services).map(async ([key, service]) => {
                try {
                    const baseUrl = this.serviceHttpUrl(key);
                    const response = await fetch(`${baseUrl}/health`, { cache: 'no-store' });
                    if (!response.ok) {
                        return { label: service.label, state: 'degraded' };
                    }
                    return { label: service.label, state: 'healthy' };
                } catch (error) {
                    return { label: service.label, state: 'error' };
                }
            })
        );
        this.renderStatus(states);
    }

    renderStatus(states) {
        if (!this.dom.status) return;
        const colorMap = {
            healthy: 'bg-green-500',
            degraded: 'bg-yellow-500',
            error: 'bg-red-500',
        };
        this.dom.status.innerHTML = states
            .map(
                ({ label, state }) => `
                <span class="inline-flex items-center px-2 py-1 text-xs font-medium bg-white rounded-full border border-gray-200 shadow-sm mr-2 mb-2">
                    <span class="w-2 h-2 ${colorMap[state]} rounded-full mr-2"></span>${label}
                </span>`
            )
            .join('');
    }
    async translateText() {
        const text = this.dom.sourceText.value.trim();
        if (!text) {
            this.showToast('请输入要翻译的文本', 'warning');
            return;
        }
        const payload = {
            text,
            source_language: this.dom.sourceLanguage.value,
            target_language: this.dom.targetLanguage.value,
        };
        await this.withButtonLoading(this.dom.translateBtn, '翻译中...', async () => {
            const response = await fetch(`${this.serviceHttpUrl('translation')}/translate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                throw new Error(`翻译服务返回状态 ${response.status}`);
            }
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '翻译失败');
            }
            const data = result.data || {};
            this.dom.translatedText.value = data.translated_text || '';
            const confidence = data.confidence != null ? `${(data.confidence * 100).toFixed(1)}%` : '未知';
            this.dom.translationInfo.textContent = `引擎: ${data.engine || '未知'} | 置信度: ${confidence}`;
            this.showToast('翻译完成', 'success');
        });
    }

    clearText() {
        this.dom.sourceText.value = '';
        this.dom.translatedText.value = '';
        this.dom.translationInfo.textContent = '等待翻译结果...';
    }

    async copyTranslation() {
        const text = this.dom.translatedText.value;
        if (!text) {
            this.showToast('没有可复制的内容', 'warning');
            return;
        }
        try {
            await navigator.clipboard.writeText(text);
            this.showToast('已复制到剪贴板', 'success');
        } catch (error) {
            this.showToast('复制失败，请检查浏览器权限', 'error');
        }
    }

    async speakText() {
        const text = this.dom.translatedText.value.trim();
        if (!text) {
            this.showToast('暂无可朗读的内容', 'warning');
            return;
        }
        const payload = {
            text,
            language_type: this.dom.targetLanguage.value,
        };
        await this.withButtonLoading(this.dom.speakBtn, '合成中...', async () => {
            const response = await fetch(`${this.serviceHttpUrl('voice')}/tts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                throw new Error(`语音合成服务返回状态 ${response.status}`);
            }
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '语音合成失败');
            }
            const { audio_base64: audioBase64, audio_format: audioFormat } = result.data || {};
            if (!audioBase64) {
                throw new Error('语音合成结果为空');
            }
            this.playAudio(audioBase64, audioFormat || 'wav');
            this.showToast('语音播放中', 'success');
        });
    }

    async playAudio(base64, format) {
        // Prefer WebAudio for better autoplay compatibility. Fallback to HTMLAudio.
        try {
            await this.ensureAudioContext();
            const ctx = this.audioContext;
            const binary = atob(base64);
            const len = binary.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);
            const buffer = await ctx.decodeAudioData(bytes.buffer.slice(0));
            if (this.activeAudioSource) {
                try { this.activeAudioSource.stop(); } catch (_) {}
            }
            const source = ctx.createBufferSource();
            source.buffer = buffer;
            const gain = ctx.createGain();
            gain.gain.value = 1.0;
            source.connect(gain);
            gain.connect(ctx.destination);
            source.start(0);
            this.activeAudioSource = source;
            return;
        } catch (err) {
            // Fallback to HTMLAudio element
            try {
                if (this.activeAudio) {
                    this.activeAudio.pause();
                }
                const audio = new Audio(`data:audio/${format};base64,${base64}`);
                audio.play().catch(() => {
                    this.showToast('浏览器阻止自动播放，请点击页面后重试', 'warning');
                });
                this.activeAudio = audio;
            } catch (error) {
                console.error('Audio playback error:', error);
                this.showToast('无法播放音频', 'error');
            }
        }
    }

    async toggleRecording() {
        if (this.isRecording) {
            await this.stopRecording();
        } else {
            await this.startRecording();
        }
    }

    async startRecording() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.showToast('当前浏览器不支持麦克风录音', 'error');
            return;
        }
        const targetLanguage = this.dom.targetLanguage.value;
        this.voiceTranslationMap = new Map();
        this.voiceTranscriptText = '';
        this.streamedAudioBytes = 0;
        this.streamLimitReached = false;
        this.voiceSessionCompleted = false;

        try {
            await this.openVoiceSocket(targetLanguage);
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: 16000,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });
            this.audioStream = stream;
            await this.ensureAudioContext();
            await this.ensureAudioWorkletModule();
            const sourceNode = this.audioContext.createMediaStreamSource(stream);
            this.audioSourceNode = sourceNode;
            const processorNode = new AudioWorkletNode(this.audioContext, 'pcm-frame-sender', {
                numberOfInputs: 1,
                numberOfOutputs: 1,
                channelCount: 1,
                outputChannelCount: [1],
            });
            this.audioProcessorNode = processorNode;
            const outputNode = this.audioContext.createGain();
            outputNode.gain.value = 0;
            this.audioOutputNode = outputNode;
            const actualRate = this.audioContext.sampleRate || 48000;
            this.audioResampler = new AudioResampler(actualRate, 16000);
            const voiceRatio = this.audioResampler.ratio || 1;
            this.voiceChunkSamples = Math.max(320, Math.round(4096 / Math.max(voiceRatio, 1)));
            this.voicePendingInt16 = new Int16Array(0);
            processorNode.port.onmessage = ({ data }) => this.handleAudioFrame(data);
            processorNode.port.onmessageerror = (event) => {
                console.error('Voice worklet message error:', event);
            };
            sourceNode.connect(processorNode);
            processorNode.connect(outputNode);
            outputNode.connect(this.audioContext.destination);

            this.isRecording = true;
            this.voiceSocketTargetLanguage = targetLanguage;
            this.updateRecordingUI(true);
            this.dom.voiceResult.innerHTML = `
                <div class="space-y-2">
                    <div>
                        <p class="text-gray-800 font-medium">转写结果</p>
                        <p class="text-sm text-gray-500 mt-1">实时识别中...</p>
                    </div>
                    <div>
                        <p class="text-gray-800 font-medium">翻译结果 (${targetLanguage || 'auto'})</p>
                        <p class="text-sm text-gray-500 mt-1">等待翻译结果...</p>
                    </div>
                </div>
            `;
            this.showToast('开始录音，实时翻译中...', 'info');
        } catch (error) {
            console.error('Recording error:', error);
            this.cleanupAudioPipeline();
            this.closeVoiceSocket(true);
            this.isRecording = false;
            this.updateRecordingUI(false);
            this.showToast(error.message || '无法启动实时语音翻译，请检查权限设置', 'error');
        }
    }

    async stopRecording() {
        if (!this.isRecording) {
            return;
        }
        this.isRecording = false;
        this.updateRecordingUI(false);

        if (this.audioResampler && !this.streamLimitReached) {
            const tail = this.audioResampler.flush();
            if (tail && tail.length) {
                this.appendVoiceSamples(tail);
            }
        }
        if (!this.streamLimitReached) {
            this.flushVoicePendingAudio(true);
        }

        this.cleanupAudioPipeline();

        if (this.voiceSocket && this.voiceSocket.readyState === WebSocket.OPEN) {
            try {
                this.voiceSocket.send(JSON.stringify({ type: 'stop' }));
            } catch (error) {
                console.warn('Failed to notify voice service stop:', error);
            }
            this.showToast('录音结束，等待翻译结果...', 'info');
        } else {
            this.showToast('录音结束', 'info');
        }
    }

    updateRecordingUI(isRecording) {
        if (isRecording) {
            this.dom.recordBtn.classList.add('recording', 'bg-red-600');
            this.dom.recordBtn.innerHTML = '<i class="fas fa-stop text-4xl"></i>';
            this.dom.recordStatus.textContent = '实时识别中...';
            this.dom.waveform.classList.remove('hidden');
        } else {
            this.dom.recordBtn.classList.remove('recording', 'bg-red-600');
            this.dom.recordBtn.innerHTML = '<i class="fas fa-microphone text-4xl"></i>';
            this.dom.recordStatus.textContent = '点击开始录音';
            this.dom.waveform.classList.add('hidden');
        }
    }

    async ensureAudioContext() {
        if (!this.audioContext) {
            const AudioContextCls = window.AudioContext || window.webkitAudioContext;
            try {
                this.audioContext = new AudioContextCls({ sampleRate: 16000 });
            } catch (error) {
                this.audioContext = new AudioContextCls();
            }
        }
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }
        return this.audioContext;
    }

    async ensureAudioWorkletModule() {
        await this.ensureAudioContext();
        if (!this.audioContext.audioWorklet) {
            throw new Error('当前浏览器不支持 AudioWorklet，请升级或更换浏览器');
        }
        if (this.audioWorkletModuleLoaded) {
            return;
        }
        if (!this.audioWorkletModuleLoading) {
            const moduleUrl = new URL('audio-worklets/pcm-frame-sender.js', window.location.origin).toString();
            this.audioWorkletModuleLoading = this.audioContext.audioWorklet
                .addModule(moduleUrl)
                .then(() => {
                    this.audioWorkletModuleLoaded = true;
                })
                .catch((error) => {
                    console.error('AudioWorklet module load failed:', error);
                    throw new Error('实时音频处理模块加载失败，请稍后重试');
                })
                .finally(() => {
                    this.audioWorkletModuleLoading = null;
                });
        }
        return this.audioWorkletModuleLoading;
    }

    async openVoiceSocket(targetLanguage) {
        return new Promise((resolve, reject) => {
            const baseUrl = this.serviceWsUrl('voice');
            const url = `${baseUrl}/voice/translate/live?target_language=${encodeURIComponent(
                targetLanguage || ''
            )}`;
            const socket = new WebSocket(url);
            socket.binaryType = 'arraybuffer';

            const handleInitialError = (event) => {
                console.error('Voice socket connection error:', event);
                socket.onopen = null;
                socket.onclose = null;
                socket.onerror = null;
                reject(new Error('实时翻译服务连接失败'));
            };

            socket.onopen = () => {
                socket.onerror = (event) => this.handleVoiceSocketError(event);
                socket.onclose = () => this.handleVoiceSocketClose();
                socket.onmessage = (event) => this.handleVoiceSocketMessage(event);
                this.voiceSocket = socket;
                resolve();
            };

            socket.onerror = handleInitialError;
            socket.onclose = (event) => {
                if (socket.readyState !== WebSocket.OPEN && this.voiceSocket !== socket) {
                    handleInitialError(event);
                }
            };
        });
    }

    handleVoiceSocketMessage(event) {
        let payload;
        try {
            payload = JSON.parse(event.data);
        } catch (error) {
            console.warn('Invalid voice payload:', event.data);
            return;
        }

        const targetLanguage = this.voiceSocketTargetLanguage || this.dom.targetLanguage.value;

        switch (payload.type) {
            case 'ready':
                this.showToast('实时语音服务已连接', 'info');
                break;
            case 'transcript':
                this.voiceTranscriptText = payload.text || '';
                this.updateVoiceStreamUI(this.voiceTranscriptText, this.voiceTranslationMap, targetLanguage);
                break;
            case 'translation':
                if (payload.language) {
                    this.voiceTranslationMap.set(payload.language, payload.text || '');
                    this.updateVoiceStreamUI(this.voiceTranscriptText, this.voiceTranslationMap, targetLanguage);
                }
                break;
            case 'done':
                this.voiceSessionCompleted = true;
                if (payload.data) {
                    this.renderVoiceResult(payload.data, targetLanguage);
                }
                this.closeVoiceSocket();
                break;
            case 'error':
                this.voiceSessionCompleted = true;
                this.dom.voiceResult.innerHTML = `
                    <p class="text-red-600 font-medium">语音识别失败</p>
                    <p class="text-sm text-gray-600">${payload.message || '请稍后重试'}</p>
                `;
                this.showToast(payload.message || '语音处理失败', 'error');
                this.closeVoiceSocket(true);
                break;
            default:
                break;
        }
    }

    handleVoiceSocketError(event) {
        console.error('Voice socket error:', event);
        this.voiceSessionCompleted = true;
        this.showToast('语音服务连接异常', 'error');
        this.closeVoiceSocket(true);
    }

    handleVoiceSocketClose() {
        const wasCompleted = this.voiceSessionCompleted;
        this.voiceSocket = null;
        if (this.isRecording) {
            this.isRecording = false;
            this.updateRecordingUI(false);
        }
        if (!wasCompleted) {
            this.showToast('语音服务连接已关闭', 'warning');
        }
        this.voiceSessionCompleted = false;
    }

    handleAudioFrame(frame) {
        if (
            !this.isRecording ||
            !this.voiceSocket ||
            this.voiceSocket.readyState !== WebSocket.OPEN ||
            this.streamLimitReached
        ) {
            return;
        }
        if (!frame) {
            return;
        }
        const inputBuffer = frame instanceof Float32Array ? frame : new Float32Array(frame);
        if (inputBuffer.length === 0) {
            return;
        }
        const resampler = this.audioResampler;
        if (!resampler) {
            return;
        }
        const chunk = resampler.process(inputBuffer);
        if (chunk && chunk.length) {
            this.appendVoiceSamples(chunk);
        }
    }

    sendAudioChunk(chunk) {
        if (!this.voiceSocket || this.voiceSocket.readyState !== WebSocket.OPEN || this.streamLimitReached) {
            return;
        }
        const payload = chunk.buffer.slice(chunk.byteOffset, chunk.byteOffset + chunk.byteLength);
        const nextTotal = this.streamedAudioBytes + payload.byteLength;
        if (nextTotal > this.maxStreamingBytes) {
            this.streamLimitReached = true;
            this.showToast('音频超过实时翻译限制，已停止录音', 'warning');
            this.stopRecording();
            return;
        }
        this.streamedAudioBytes = nextTotal;
        try {
            this.voiceSocket.send(payload);
        } catch (error) {
            console.error('Failed to send audio chunk:', error);
            this.streamLimitReached = true;
            this.showToast('语音数据发送失败', 'error');
            this.stopRecording();
        }
    }

    appendVoiceSamples(samples) {
        if (!samples || !samples.length) {
            return;
        }
        this.voicePendingInt16 = this.concatInt16Arrays(this.voicePendingInt16, samples);
        this.flushVoicePendingAudio();
    }

    flushVoicePendingAudio(force = false) {
        const chunkSize = this.voiceChunkSamples || 0;
        if (!chunkSize) {
            if (force && this.voicePendingInt16.length > 0) {
                this.sendAudioChunk(this.voicePendingInt16);
                this.voicePendingInt16 = new Int16Array(0);
            }
            return;
        }
        while (this.voicePendingInt16.length >= chunkSize) {
            const frame = this.voicePendingInt16.slice(0, chunkSize);
            this.sendAudioChunk(frame);
            this.voicePendingInt16 = this.voicePendingInt16.slice(chunkSize);
        }
        if (force && this.voicePendingInt16.length > 0) {
            this.sendAudioChunk(this.voicePendingInt16);
            this.voicePendingInt16 = new Int16Array(0);
        }
    }

    cleanupAudioPipeline() {
        if (this.audioProcessorNode) {
            try {
                this.audioProcessorNode.disconnect();
            } catch (_) {}
            if (this.audioProcessorNode.port) {
                this.audioProcessorNode.port.onmessage = null;
                this.audioProcessorNode.port.onmessageerror = null;
                try {
                    this.audioProcessorNode.port.close();
                } catch (_) {}
            }
            this.audioProcessorNode = null;
        }
        if (this.audioSourceNode) {
            try {
                this.audioSourceNode.disconnect();
            } catch (_) {
                // ignore disconnect errors
            }
            this.audioSourceNode = null;
        }
        if (this.audioOutputNode) {
            try {
                this.audioOutputNode.disconnect();
            } catch (_) {
                // ignore disconnect errors
            }
            this.audioOutputNode = null;
        }
        if (this.audioStream) {
            this.audioStream.getTracks().forEach((track) => track.stop());
            this.audioStream = null;
        }
        this.audioResampler = null;
        this.voicePendingInt16 = new Int16Array(0);
    }

    closeVoiceSocket(force = false) {
        if (!this.voiceSocket) {
            return;
        }
        const socket = this.voiceSocket;
        this.voiceSocket = null;
        try {
            if (force && socket.readyState === WebSocket.OPEN) {
                socket.close(1011, 'client-close');
            } else {
                socket.close();
            }
        } catch (error) {
            console.warn('Voice socket close error:', error);
        }
    }
    updateVoiceStreamUI(transcriptText, translationMap, targetLanguage, requestId = null) {
        const targetTranslation = translationMap.get(targetLanguage);
        const otherTranslations = Array.from(translationMap.entries())
            .filter(([language]) => language !== targetLanguage)
            .map(([language, text]) => `${language}: ${text}`)
            .join('；');

        const translationBlock = targetTranslation || otherTranslations
            ? `<p class="text-sm text-gray-700 mt-1">${targetTranslation || otherTranslations}</p>`
            : '<p class="text-sm text-gray-500 mt-1">等待翻译结果...</p>';

        this.dom.voiceResult.innerHTML = `
            <div class="space-y-2">
                <div>
                    <p class="text-gray-800 font-medium">转写结果</p>
                    <p class="text-sm text-gray-700 mt-1">${transcriptText || '正在识别...'}</p>
                </div>
                <div>
                    <p class="text-gray-800 font-medium">翻译结果 (${targetLanguage})</p>
                    ${translationBlock}
                </div>
                ${requestId ? `<p class="text-xs text-gray-500">请求 ID: ${requestId}</p>` : ''}
            </div>
        `;
    }

    renderVoiceResult(data, targetLanguage) {
        const transcripts = data.transcripts || data.transcription || [];
        const translations = data.translations || data.translation || [];
        const transcriptText = Array.isArray(transcripts) ? transcripts.join(' ') : String(transcripts || '');

        const translationMap = new Map();
        if (Array.isArray(translations)) {
            translations.forEach((item) => {
                if (item && item.language) {
                    translationMap.set(item.language, item.text);
                }
            });
        }
        this.updateVoiceStreamUI(transcriptText, translationMap, targetLanguage, data.request_id || null);

        if (transcriptText) {
            this.dom.sourceText.value = transcriptText;
        }
        const targetTranslation = translationMap.get(targetLanguage);
        if (targetTranslation) {
            this.dom.translatedText.value = targetTranslation;
            this.dom.translationInfo.textContent = '语音翻译结果已填充';
        }
        this.showToast('语音处理完成', 'success');
    }
    async startCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.showToast('当前浏览器不支持摄像头调用', 'error');
            return;
        }
        try {
            this.cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
            this.dom.cameraPreview.srcObject = this.cameraStream;
            this.dom.cameraPreview.classList.remove('hidden');
            this.dom.cameraPlaceholder.classList.add('hidden');
            this.dom.startCameraBtn.classList.add('hidden');
            this.dom.stopCameraBtn.classList.remove('hidden');
            this.dom.captureBtn.disabled = false;
            this.showToast('摄像头已开启', 'success');
        } catch (error) {
            console.error('Camera error:', error);
            this.showToast('无法访问摄像头，请检查权限设置', 'error');
        }
    }

    stopCamera() {
        if (this.cameraStream) {
            this.cameraStream.getTracks().forEach((track) => track.stop());
            this.cameraStream = null;
        }
        this.dom.cameraPreview.srcObject = null;
        this.dom.cameraPreview.classList.add('hidden');
        this.dom.cameraPlaceholder.classList.remove('hidden');
        this.dom.startCameraBtn.classList.remove('hidden');
        this.dom.stopCameraBtn.classList.add('hidden');
        this.dom.captureBtn.disabled = true;
        this.showToast('摄像头已关闭', 'info');
    }

    async capturePhoto() {
        if (!this.cameraStream) {
            this.showToast('请先开启摄像头', 'warning');
            return;
        }
        const video = this.dom.cameraPreview;
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.9);

        this.dom.cameraResult.innerHTML = `
            <p class="text-gray-700">图片已捕获，正在请求场景识别...</p>
        `;

        try {
            const contextHint = this.dom.sceneText.value.trim();
            const response = await fetch(`${this.serviceHttpUrl('scene')}/recognize`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    images: [dataUrl],
                    prompt: contextHint
                        ? `结合以下对话背景分析画面并给出翻译策略：${contextHint}`
                        : '分析画面并识别场景，给出翻译策略建议。',
                }),
            });
            if (!response.ok) {
                throw new Error(`场景识别服务返回状态 ${response.status}`);
            }
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '场景识别失败');
            }
            this.renderCameraResult(result.data || {}, dataUrl);
        } catch (error) {
            console.error('Scene recognition error:', error);
            this.dom.cameraResult.innerHTML = `
                <p class="text-red-600 font-medium">场景识别失败</p>
                <p class="text-sm text-gray-600">${error.message || '请检查服务状态后再试'}</p>
            `;
            this.showToast('场景识别失败', 'error');
        }
    }

    renderCameraResult(data, imageDataUrl) {
        const settings = data.recommended_settings || {};
        this.dom.cameraResult.innerHTML = `
            <div class="space-y-3">
                <img src="${imageDataUrl}" alt="captured" class="w-full rounded-lg border border-gray-200">
                <div>
                    <p class="text-gray-800 font-medium">识别场景</p>
                    <p class="text-sm text-gray-700 mt-1">${data.scenario_name || '未识别'}</p>
                </div>
                <div>
                    <p class="text-gray-800 font-medium">置信度</p>
                    <p class="text-sm text-gray-700 mt-1">${data.confidence != null ? data.confidence : '未知'}</p>
                </div>
                <div>
                    <p class="text-gray-800 font-medium">总结</p>
                    <p class="text-sm text-gray-700 mt-1">${data.summary || '暂无总结'}</p>
                </div>
                <div>
                    <p class="text-gray-800 font-medium">推荐设置</p>
                    <p class="text-sm text-gray-700 mt-1">
                        风格：${settings.response_style || '—'}；
                        正式程度：${settings.formality_level || '—'}；
                        文化适配：${settings.cultural_adaptation ? '需要' : '无需'}
                    </p>
                </div>
            </div>
        `;
        this.showToast('场景识别完成', 'success');
    }
    async recognizeScene() {
        const text = this.dom.sceneText.value.trim();
        if (!text) {
            this.showToast('请输入对话内容后再分析', 'warning');
            return;
        }
        await this.withButtonLoading(this.dom.recognizeBtn, '分析中...', async () => {
            const response = await fetch(`${this.serviceHttpUrl('scene')}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ context_text: text }),
            });
            if (!response.ok) {
                throw new Error(`文本分析服务返回状态 ${response.status}`);
            }
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '分析失败');
            }
            this.renderSceneAnalysis(result.data || {});
        });
    }

    renderSceneAnalysis(data) {
        const sentiment = data.sentiment || data.mood || '未知';
        const topics = data.topics || data.keywords || [];
        const notes = data.notes || data.summary || '暂无额外说明';
        this.dom.sceneResult.innerHTML = `
            <div class="space-y-2">
                <div>
                    <p class="text-gray-800 font-medium">情绪倾向</p>
                    <p class="text-sm text-gray-700 mt-1">${Array.isArray(sentiment) ? sentiment.join('、') : sentiment}</p>
                </div>
                <div>
                    <p class="text-gray-800 font-medium">核心话题</p>
                    <p class="text-sm text-gray-700 mt-1">${Array.isArray(topics) && topics.length ? topics.join('、') : '未识别'}</p>
                </div>
                <div>
                    <p class="text-gray-800 font-medium">建议</p>
                    <p class="text-sm text-gray-700 mt-1">${notes}</p>
                </div>
            </div>
        `;
        this.showToast('场景文本分析完成', 'success');
    }

    appendSceneMessage(role, content) {
        this.sceneHistory.push({ role, content });
        if (this.sceneHistory.length > 30) {
            this.sceneHistory = this.sceneHistory.slice(-30);
        }
        this.renderSceneChat();
    }

    renderSceneChat() {
        if (!this.dom.sceneChat) return;
        this.dom.sceneChat.innerHTML = this.sceneHistory
            .map((msg) => {
                const alignment = msg.role === 'user' ? 'items-end' : 'items-start';
                const bubbleColor = msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800';
                return `
                    <div class="flex ${alignment}">
                        <div class="max-w-[85%] px-4 py-2 rounded-2xl ${bubbleColor}">
                            ${msg.content.replace(/\n/g, '<br>')}
                        </div>
                    </div>
                `;
            })
            .join('');
        this.dom.sceneChat.scrollTop = this.dom.sceneChat.scrollHeight;
    }

    async sendSceneMessage() {
        const text = this.dom.sceneChatInput.value.trim();
        if (!text) {
            this.showToast('请输入要发送的内容', 'warning');
            return;
        }
        this.dom.sceneChatInput.value = '';
        this.appendSceneMessage('user', text);
        this.dom.sceneSendBtn.disabled = true;
        try {
            const payload = {
                history: this.sceneHistory.map((item) => ({ role: item.role, content: item.content })),
                scenario: this.dom.sceneText.value.trim() || 'general',
                language: this.dom.targetLanguage.value || 'zh',
            };
            const response = await fetch(`${this.serviceHttpUrl('scene')}/dialogue`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                throw new Error(`场景对话服务返回状态 ${response.status}`);
            }
            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || '对话生成失败');
            }
            const reply = result.data?.reply || '已记录。';
            this.appendSceneMessage('assistant', reply);
        } catch (error) {
            console.error('Scene dialogue error:', error);
            this.appendSceneMessage('assistant', `对话辅导失败：${error.message || '请稍后重试。'}`);
        } finally {
            this.dom.sceneSendBtn.disabled = false;
        }
    }

    resetSceneDialogue(initial = false) {
        this.sceneHistory = [
            {
                role: 'assistant',
                content: initial
                    ? '欢迎使用场景对话助手，描述场景或直接提问，我会提供翻译策略建议。'
                    : '会话已重置，如需帮助请重新输入问题。',
            },
        ];
        this.renderSceneChat();
        if (!initial) {
            this.showToast('场景对话已重置', 'info');
        }
    }
    async withButtonLoading(button, loadingText, action) {
        if (!button) {
            await action();
            return;
        }
        const originalHtml = button.innerHTML;
        button.disabled = true;
        button.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i>${loadingText}`;
        try {
            await action();
        } catch (error) {
            console.error('Action error:', error);
            this.showToast(error.message || '操作失败，请稍后重试', 'error');
        } finally {
            button.disabled = false;
            button.innerHTML = originalHtml;
        }
    }

    showToast(message, type = 'info') {
        if (!this.dom.toast) return;
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle',
        };
        const colors = {
            success: 'bg-green-600',
            error: 'bg-red-600',
            warning: 'bg-yellow-600',
            info: 'bg-blue-600',
        };
        this.dom.toast.className = `fixed bottom-4 right-4 ${colors[type]} text-white px-6 py-3 rounded-lg shadow-lg transform transition-transform duration-300 z-50`;
        this.dom.toastIcon.className = `fas ${icons[type]} mr-2`;
        this.dom.toastMessage.textContent = message;
        this.dom.toast.classList.remove('translate-y-full');
        clearTimeout(this.toastTimer);
        this.toastTimer = setTimeout(() => {
            this.dom.toast.classList.add('translate-y-full');
        }, 3000);
    }

}

document.addEventListener('DOMContentLoaded', () => {
    window.gummyTranslator = new GummyTranslator();
});
