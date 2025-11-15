class PCMFrameSenderProcessor extends AudioWorkletProcessor {
    constructor(options) {
        super();
        const processorOptions = (options && options.processorOptions) || {};
        this.channelIndex = Number.isInteger(processorOptions.channelIndex) ? processorOptions.channelIndex : 0;
    }

    process(inputs) {
        const input = inputs[0];
        if (!input || input.length === 0) {
            return true;
        }
        const channelData = input[this.channelIndex] || input[0];
        if (!channelData || channelData.length === 0) {
            return true;
        }

        const copy = new Float32Array(channelData.length);
        copy.set(channelData);
        this.port.postMessage(copy, [copy.buffer]);

        return true;
    }
}

registerProcessor('pcm-frame-sender', PCMFrameSenderProcessor);
