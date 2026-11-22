import KeenASR from './sdk/keenasr-web.js';

const events = [];
let context;
let origin;
let sourceStart;
let deliveredEnd = false;
let destination;

async function replay() {
    window.keenStage = 'opening recording';
    const config = await (await fetch('/case.json')).json();
    context = new AudioContext({sampleRate: 16000});
    await context.resume();
    const recording = await context.decodeAudioData(await (await fetch('/recording.wav')).arrayBuffer());
    if (recording.sampleRate !== 16000 || recording.numberOfChannels !== 1 ||
        recording.length !== Math.round(config.duration_seconds * 16000)) {
        throw new Error('Decoded source differs from the frozen mono recording.');
    }
    const pcm = context.createBuffer(1, recording.length + Math.round(config.tail_seconds * 16000), 16000);
    pcm.copyToChannel(recording.getChannelData(0), 0);

    // Supply only a silent destination or the selected recording stream.
    // The physical microphone and audio output are never connected.
    navigator.mediaDevices.getUserMedia = async (constraints) => {
        if (!constraints?.audio || constraints.video) throw new Error('Unexpected capture request.');
        destination = context.createMediaStreamDestination();
        return destination.stream;
    };
    window.keenStage = 'checking synthetic input';
    await KeenASR.requestMicrophoneAccess(() => {});
    window.keenStage = 'initializing SDK';
    await KeenASR.initialize({
        asrBundleURL: new URL(config.bundle_path, location.href),
        onCoreReady() { window.keenStage = 'loading acoustic bundle'; },
        onASRBundleReady() { window.keenStage = 'acoustic bundle ready'; },
    });
    window.keenStage = 'building book graph';
    const graph = `benchmark_${config.id.replace(/[^A-Za-z0-9_]/g, '_')}`;
    const built = await KeenASR.createDecodingGraphFromPhrases(graph, [config.keen_book_text], {
        speakingTaskType: KeenASR.SpeakingTask.ORAL_READING,
    });
    if (!built) throw new Error('Keen could not create the book graph.');
    await KeenASR.prepareForListeningWithDecodingGraphWithName(graph);
    KeenASR.setVADParameters({
        timeoutForNoSpeech: 30,
        timeoutEndSilenceForGoodMatch: 120,
        timeoutEndSilenceForAnyMatch: 120,
        timeoutMaxDuration: Math.ceil(pcm.duration + 2.5),
    });

    function record(result, final) {
        if (origin === undefined || context.currentTime < sourceStart) return;
        events.push({
            kind: 'transcript',
            text: result?.text ?? '',
            wall_seconds: (performance.now() - origin) / 1000,
            delivered_audio_seconds: Math.min(pcm.duration, context.currentTime - sourceStart),
            final,
        });
    }
    KeenASR.onPartialResult = result => record(result, false);
    KeenASR.onFinalResponse = response => {
        record(response.asrResult, true);
        const final = events.at(-1);
        const complete = deliveredEnd || context.currentTime >= sourceStart + pcm.duration;
        window.keenTrial = {events, sdk_version: response.sdkVersion, bundle: response.asrBundle,
            audio_context_rate: context.sampleRate, delivered_end: complete,
            status: complete && final?.final && final.text.trim() ? 'ok' : 'failed',
            final_text: final?.text || '',
            error: complete && final?.final && final.text.trim() ? undefined : 'The SDK ended early or returned no text.'};
    };
    window.keenStage = 'starting synthetic input';
    await KeenASR.startListening();
    if (!destination) throw new Error('The SDK did not request a replay stream.');
    const source = context.createBufferSource();
    source.buffer = pcm;
    source.connect(destination);
    sourceStart = context.currentTime + 0.25;
    origin = performance.now() + (sourceStart - context.currentTime) * 1000;
    source.onended = () => {
        deliveredEnd = true;
        events.push({kind: 'end_of_capture', wall_seconds: (performance.now() - origin) / 1000,
            samples: pcm.length});
    };
    source.start(sourceStart);
    window.keenStage = 'playing into synthetic input';
}

replay().catch(error => {
    window.keenTrial = {status: 'failed', error: String(error), stage: window.keenStage, events};
});
