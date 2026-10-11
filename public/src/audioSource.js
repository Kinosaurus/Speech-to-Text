/**
 * Audio source switch: live microphone OR a recorded audio file.
 *
 * The KeenASR web SDK has no "process this file" API. Every time listening
 * starts it calls navigator.mediaDevices.getUserMedia() and feeds the
 * resulting stream into its audio worklet. This module wraps getUserMedia:
 *
 *   - 'microphone' mode  -> passes straight through to the real microphone
 *   - 'recording' mode   -> returns a stream that plays the chosen file
 *
 * The recording plays in real time, exactly like someone speaking, so the
 * rest of the app (partial results, VAD, checkpoints) behaves the same.
 *
 * Because the SDK calls getUserMedia on every start, the mode can be changed
 * between reading attempts without re-initialising KeenASR.
 */

// Silence before the recording starts, giving the SDK time to wire up its
// audio graph so the first words are not clipped.
const LEAD_IN_SECONDS = 1.0;

let installed = false;
let realGetUserMedia = null;
let mode = 'microphone';
let audioContext = null;
let recording = null; // { name, buffer }

function getContext() {
  if (!audioContext) audioContext = new AudioContext();
  return audioContext;
}

async function createRecordingStream() {
  const ctx = getContext();
  if (ctx.state === 'suspended') await ctx.resume();

  const destination = ctx.createMediaStreamDestination();
  destination.channelCount = 1; // mono, like a microphone

  // No recording chosen yet (e.g. during initialisation): a silent stream.
  if (!recording) return destination.stream;

  const source = ctx.createBufferSource();
  source.buffer = recording.buffer;
  source.connect(destination);
  source.start(ctx.currentTime + LEAD_IN_SECONDS);

  const stopPlayback = () => {
    try { source.stop(); } catch { /* already stopped */ }
    try { source.disconnect(); } catch { /* already disconnected */ }
  };

  // When the SDK stops the "microphone" (the Stop button, or the SDK's own
  // probe during initialisation) the recording must stop too.
  for (const track of destination.stream.getTracks()) {
    const originalStop = track.stop.bind(track);
    track.stop = () => {
      stopPlayback();
      originalStop();
    };
  }

  return destination.stream;
}

/** Call once, before KeenASR is used. Safe to call repeatedly. */
export function installAudioSource() {
  if (installed || !navigator.mediaDevices?.getUserMedia) return;

  realGetUserMedia = navigator.mediaDevices.getUserMedia.bind(
    navigator.mediaDevices
  );

  navigator.mediaDevices.getUserMedia = async (constraints) => {
    const wantsAudioOnly = constraints?.audio && !constraints?.video;

    if (mode === 'recording' && wantsAudioOnly) {
      return createRecordingStream();
    }

    return realGetUserMedia(constraints);
  };

  installed = true;
}

export function setAudioMode(newMode) {
  if (newMode !== 'microphone' && newMode !== 'recording') {
    throw new Error(`Unknown audio mode: ${newMode}`);
  }
  mode = newMode;
}

export function getAudioMode() {
  return mode;
}

/** Decode and remember a recording (File, Blob or ArrayBuffer). */
export async function setRecording(data, name = 'recording') {
  const bytes = data instanceof ArrayBuffer ? data : await data.arrayBuffer();
  const buffer = await getContext().decodeAudioData(bytes);

  recording = { name, buffer };
  return { name, durationSeconds: buffer.duration };
}

export async function setRecordingFromUrl(url, name) {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Cannot load recording (HTTP ${response.status}).`);
  }

  return setRecording(await response.arrayBuffer(), name);
}

export function hasRecording() {
  return recording !== null;
}
