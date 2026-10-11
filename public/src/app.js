
import { jsx, jsxs, Fragment } from
  'https://esm.sh/preact@10.13.2/jsx-runtime';

import { render } from
  'https://esm.sh/preact@10.13.2';

import {
  useState,
  useRef,
  useEffect
} from 'https://esm.sh/preact@10.13.2/hooks';

import KeenASR, { TextAligner } from '../vendor/keenasr/keenasr-web.js';
import { createCheckpointEngine } from './checkpointEngine.js';
import { normalize, getWords } from './textUtils.js';
import {
  installAudioSource,
  setAudioMode,
  setRecording,
  setRecordingFromUrl,
  hasRecording
} from './audioSource.js';

// Must run before KeenASR asks for the microphone.
installAudioSource();

// --------------------------------------------------
// Configuration
// --------------------------------------------------

// Folder name under public/books/ containing full_text.txt and checkpoints.json
const BOOK_NAME = 'little-mermaid';

const TEXT_URL = new URL(
  `../books/${BOOK_NAME}/full_text.txt`,
  import.meta.url
);
const CHECKPOINTS_URL = new URL(
  `../books/${BOOK_NAME}/checkpoints.json`,
  import.meta.url
);

// Optional list of bundled test recordings (see public/test-audio/README.md).
const TEST_AUDIO_URL = new URL('../test-audio/', import.meta.url);

// KeenASR acoustic model bundle (not committed; see README).
const MODEL_URL = new URL(
  '../vendor/keenasr/models/keenAK3m-nnet3chain-en-us.tgz',
  import.meta.url
);

let readingText = '';
let bookConfig = null;
let textAligner = null;
let decodingGraphName = '';

function logEvent(message) {
  console.log(`[KeenASR Reading Pod] ${message}`);
}

// --------------------------------------------------
// Load and validate the two input files
// --------------------------------------------------

async function loadReadingFiles() {
  const [textResponse, jsonResponse] = await Promise.all([
    fetch(TEXT_URL),
    fetch(CHECKPOINTS_URL)
  ]);

  if (!textResponse.ok) {
    throw new Error(
      `Cannot load full_text.txt (HTTP ${textResponse.status}).`
    );
  }

  if (!jsonResponse.ok) {
    throw new Error(
      `Cannot load checkpoints.json (HTTP ${jsonResponse.status}).`
    );
  }

  const loadedText = (await textResponse.text()).trim();
  const loadedConfig = await jsonResponse.json();

  if (!loadedText) {
    throw new Error('full_text.txt is empty.');
  }

  if (!Array.isArray(loadedConfig.checkpoints)) {
    throw new Error(
      'checkpoints.json must contain a checkpoints array.'
    );
  }

  if (
    loadedConfig.book_id &&
    loadedConfig.checkpoints.some(
      checkpoint =>
        checkpoint.book_id &&
        checkpoint.book_id !== loadedConfig.book_id
    )
  ) {
    throw new Error(
      'A checkpoint book_id does not match the main book_id.'
    );
  }

  const words = getWords(loadedText);
  const errors = [];

  for (const checkpoint of loadedConfig.checkpoints) {
    const {
      id,
      checkpoint_text,
      word_start,
      word_end
    } = checkpoint;

    if (
      typeof checkpoint_text !== 'string' ||
      !Number.isInteger(word_start) ||
      !Number.isInteger(word_end) ||
      word_start < 0 ||
      word_end <= word_start ||
      word_end > words.length
    ) {
      errors.push(`${id}: invalid checkpoint text or word positions.`);
      continue;
    }

    // word_start is inclusive; word_end is exclusive.
    const phraseAtPosition = normalize(
      words.slice(word_start, word_end).join(' ')
    );

    const expectedPhrase = normalize(checkpoint_text);

    if (phraseAtPosition !== expectedPhrase) {
      errors.push(
        `${id}: word positions point to ` +
        `"${words.slice(word_start, word_end).join(' ')}", ` +
        `not "${checkpoint_text}".`
      );
    }
  }

  if (errors.length) {
    throw new Error(
      'Checkpoint validation failed:\n' + errors.join('\n')
    );
  }

  // Sort a copy so the original JSON order remains unchanged.
  loadedConfig.checkpoints.sort(
    (a, b) => a.checkpoint_position - b.checkpoint_position
  );

  readingText = loadedText;
  bookConfig = loadedConfig;

  logEvent(`Loaded book: ${loadedConfig.title || loadedConfig.book_id}`);
  logEvent(`Loaded ${words.length} whitespace-separated words.`);
  logEvent(
    `Validated ${loadedConfig.checkpoints.length} checkpoints.`
  );

  return { text: loadedText, config: loadedConfig };
}

// --------------------------------------------------
// Main application
// --------------------------------------------------

function App() {
  const [status, setStatus] = useState('Loading files...');
  const [error, setError] = useState('');
  const [passage, setPassage] = useState('');
  const [bookTitle, setBookTitle] = useState('KeenASR Reading Pod');
  const [checkpoints, setCheckpoints] = useState([]);
  const [events, setEvents] = useState([]);
  const [transcript, setTranscript] = useState('');
  const [isReady, setIsReady] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [furthestWord, setFurthestWord] = useState(-1);
  const [metrics, setMetrics] = useState(null);
  const [audioMode, setAudioModeState] = useState('microphone');
  const [recordingInfo, setRecordingInfo] = useState('');
  const [bundledRecordings, setBundledRecordings] = useState([]);

  const engineRef = useRef(null);
  const listeningRef = useRef(false);
  const mountedRef = useRef(true);
  const initRef = useRef(false);
  const stoppingRef = useRef(false);
  const stopTimerRef = useRef(null);

  // Called once the previous attempt has really finished, so a late final
  // result can never end the next attempt.
  function finishStopping() {
    clearTimeout(stopTimerRef.current);
    stoppingRef.current = false;
    setIsStopping(false);
  }

  function appendEvent(message) {
    logEvent(message);

    setEvents(previous => [
      `${new Date().toLocaleTimeString()} — ${message}`,
      ...previous
    ].slice(0, 30));
  }

  function updateCheckpointView(states) {
    setCheckpoints(states);
  }

  function handleAlignment(alignment, spokenText, isFinal = false) {
    if (!engineRef.current) return;

    const result = engineRef.current.update(
      alignment,
      spokenText,
      isFinal
    );

    if (Number.isInteger(result.furthestIndex)) {
      setFurthestWord(result.furthestIndex);
    }

    updateCheckpointView(result.checkpoints);
  }

  // Load both files when the page opens.
  useEffect(() => {
    mountedRef.current = true;

    loadReadingFiles()
      .then(({ text, config }) => {
        if (!mountedRef.current) return;

        setPassage(text);
        setBookTitle(config.title || config.book_id);
        setCheckpoints(
          config.checkpoints.map(checkpoint => ({
            ...checkpoint,
            status: 'pending'
          }))
        );
        setStatus('Files loaded. Initialize KeenASR to begin.');
      })
      .catch(error => {
        console.error(error);
        if (!mountedRef.current) return;
        setError(error.message || String(error));
        setStatus('File loading failed.');
      });

    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Optional bundled recordings listed in test-audio/recordings.json.
  useEffect(() => {
    fetch(new URL('recordings.json', TEST_AUDIO_URL))
      .then(response => (response.ok ? response.json() : []))
      .then(list => {
        if (Array.isArray(list)) setBundledRecordings(list);
      })
      .catch(() => {});
  }, []);

  function changeAudioMode(mode) {
    if (isListening || isStopping) return;

    setAudioMode(mode);
    setAudioModeState(mode);
    setError('');
    appendEvent(
      mode === 'recording'
        ? 'Audio source: recorded audio.'
        : 'Audio source: live microphone.'
    );
  }

  async function chooseRecordingFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const info = await setRecording(file, file.name);
      setRecordingInfo(
        `${info.name} (${info.durationSeconds.toFixed(1)} s)`
      );
      setError('');
      appendEvent(`Loaded recording: ${info.name}`);
    } catch (loadError) {
      console.error(loadError);
      setRecordingInfo('');
      setError(
        'Could not decode that audio file. Try a WAV or MP3.\n' +
        (loadError?.message || String(loadError))
      );
    }
  }

  async function chooseBundledRecording(event) {
    const file = event.target.value;
    if (!file) return;

    const entry = bundledRecordings.find(item => item.file === file);

    try {
      const info = await setRecordingFromUrl(
        new URL(file, TEST_AUDIO_URL),
        entry?.label || file
      );
      setRecordingInfo(
        `${info.name} (${info.durationSeconds.toFixed(1)} s)`
      );
      setError('');
      appendEvent(`Loaded recording: ${info.name}`);
    } catch (loadError) {
      console.error(loadError);
      setRecordingInfo('');
      setError(loadError?.message || String(loadError));
    }
  }

  // Initialize KeenASR after the user clicks the button.
  async function initialize() {
    if (initRef.current) return;

    initRef.current = true;
    setError('');
    setStatus('Initializing KeenASR...');

    try {
      if (!readingText || !bookConfig) {
        await loadReadingFiles();
        setPassage(readingText);
        setBookTitle(bookConfig.title || bookConfig.book_id);
        setCheckpoints(
          bookConfig.checkpoints.map(checkpoint => ({
            ...checkpoint,
            status: 'pending'
          }))
        );
      }

      const supported = KeenASR.isBrowserSupported();

      if (!supported) {
        throw new Error(
          'This browser does not support the required KeenASR features. ' +
          'Try a recent version of Chrome.'
        );
      }

      setStatus('Requesting microphone permission...');

      await KeenASR.requestMicrophoneAccess(() => {});

      setStatus('Loading speech model...');

      await KeenASR.initialize({
        asrBundleURL: MODEL_URL,
        onCoreReady: () => {
          logEvent('KeenASR core is ready.');
        },
        onASRBundleReady: () => {
          logEvent('Speech model bundle is ready.');
        }
      });

      // Change this suffix if you modify the passage but keep the same
      // book_id and your SDK caches decoding graphs.
      const graphHash = readingText
        .split('')
        .reduce((hash, char) =>
          ((hash * 31) + char.charCodeAt(0)) | 0, 0);

      const safeBookId = String(bookConfig.book_id || 'reading_book')
        .replace(/[^A-Za-z0-9_]/g, '_');

      decodingGraphName = `${safeBookId}_${Math.abs(graphHash)}`;

      setStatus('Preparing oral-reading decoder...');

      await KeenASR.createDecodingGraphFromPhrases(
        decodingGraphName,
        [readingText],
        {
          speakingTaskType: KeenASR.SpeakingTask.ORAL_READING
        }
      );

      await KeenASR.prepareForListeningWithDecodingGraphWithName(
        decodingGraphName
      );

      textAligner = new TextAligner(readingText, KeenASR);

      engineRef.current = createCheckpointEngine(
        bookConfig,
        event => {
          appendEvent(event.message);

          if (event.type === 'triggered') {
            // Hook your projector or sound-effect controller here later.
            // This demo logs the event only; it does not play effects.
          }
        }
      );

      KeenASR.setVADParameters({
        timeoutForNoSpeech: 10,
        timeoutEndSilenceForGoodMatch: 5,
        timeoutEndSilenceForAnyMatch: 5,
        timeoutMaxDuration: 30
      });

      // Process every partial result to maintain incremental alignment.
      KeenASR.onPartialResult = partialResult => {
        const partialText = partialResult?.text ?? '';

        if (!partialText || !textAligner) return;

        setTranscript(partialText);

        try {
          const alignment = textAligner.incrementalAlign(
            partialText
          );

          handleAlignment(alignment, partialText);
        } catch (alignmentError) {
          console.error('Partial alignment error:', alignmentError);
        }
      };

      // Process the final result before resetting for the next attempt.
      KeenASR.onFinalResponse = async finalResponse => {
        const asrResult =
          finalResponse?.asrResult ??
          finalResponse?.result ??
          {};

        const finalText = asrResult.text ?? '';

        setTranscript(finalText);

        let alignment = null;

        try {
          if (textAligner && finalText) {
            alignment = textAligner.incrementalAlign(finalText);
            handleAlignment(alignment, finalText, true);
          }
        } catch (alignmentError) {
          console.error('Final alignment error:', alignmentError);
        }

        if (alignment) {
          const accuracy =
            Number.isFinite(alignment.matches) &&
            Number.isFinite(alignment.refLength) &&
            alignment.refLength > 0
              ? (alignment.matches / alignment.refLength) * 100
              : null;

          setMetrics({
            accuracy,
            wordErrorRate: alignment.wordErrorRate ?? null
          });
        }

        listeningRef.current = false;
        setIsListening(false);
        finishStopping();
        setStatus('Reading attempt finished.');

        appendEvent('Final recognition result received.');

        // Audio is optional for this basic demo.
        // The checkpoint trigger logic does not depend on audio playback.
      };

      setIsReady(true);
      setStatus('Ready. Click Start Reading.');
      appendEvent('KeenASR initialization complete.');
    } catch (initializationError) {
      console.error(initializationError);
      setError(
        initializationError?.message ||
        String(initializationError)
      );
      setStatus('Initialization failed.');
      initRef.current = false;
    }
  }

  async function startReading() {
    if (!isReady || listeningRef.current || stoppingRef.current) return;

    if (audioMode === 'recording' && !hasRecording()) {
      setError('Choose a recording first, or switch to the live microphone.');
      return;
    }

    setError('');
    setMetrics(null);
    setTranscript('');
    setFurthestWord(-1);

    if (engineRef.current) {
      engineRef.current.reset();
      updateCheckpointView(engineRef.current.getStates());
    }

    // Reset the aligner before starting the next attempt.
    if (textAligner && typeof textAligner.reset === 'function') {
      textAligner.reset();
    }

    listeningRef.current = true;
    setIsListening(true);
    setStatus('Listening. Read the passage aloud.');

    try {
      KeenASR.setVADParameters({
        timeoutForNoSpeech: 10,
        timeoutEndSilenceForGoodMatch: 5,
        timeoutEndSilenceForAnyMatch: 5,
        timeoutMaxDuration: 30
      });

      await KeenASR.startListening();
    } catch (startError) {
      listeningRef.current = false;
      setIsListening(false);
      setStatus('Could not start listening.');
      setError(startError?.message || String(startError));
    }
  }

  async function stopReading() {
    if (!listeningRef.current || stoppingRef.current) return;

    stoppingRef.current = true;
    setIsStopping(true);
    setStatus('Stopping and waiting for final recognition...');

    // Safety net: if no final result ever arrives, unlock the buttons.
    stopTimerRef.current = setTimeout(() => {
      listeningRef.current = false;
      setIsListening(false);
      finishStopping();
      setStatus('Reading attempt finished.');
    }, 4000);

    try {
      console.log(
        'Recognizer state before stop:',
        KeenASR.getRecognizerState?.()
      );

      KeenASR.setVADParameters({
        timeoutForNoSpeech: 0.2,
        timeoutEndSilenceForGoodMatch: 0.2,
        timeoutEndSilenceForAnyMatch: 0.2,
        timeoutMaxDuration: 30
      });

      await KeenASR.stopListening();
    } catch (stopError) {
      // The recognizer may already have finished on its own.
      console.warn('stopListening failed:', stopError);
      listeningRef.current = false;
      setIsListening(false);
      finishStopping();
      setStatus('Reading attempt finished.');
    }
  }

  const checkpointElements = checkpoints.map(checkpoint => {
    const statusLabel = checkpoint.status || 'pending';

    return jsx('div', {
      class: 'checkpoint',
      children: jsxs(Fragment, {
        children: [
          jsx('strong', {
            children: `${checkpoint.checkpoint_position}. ${checkpoint.id}`
          }),
          jsx('div', {
            children: checkpoint.checkpoint_text
          }),
          jsx('div', {
            children: `Status: ${statusLabel}`
          }),
          jsx('small', {
            children:
              `Words ${checkpoint.word_start}–${checkpoint.word_end - 1}`
          })
        ]
      })
    }, checkpoint.id);
  });

  return jsxs('main', {
    children: [
      jsx('h1', { children: bookTitle }),
      jsx('p', { children: 'KeenASR oral-reading checkpoint test' }),

      jsx('p', {
        children: jsxs(Fragment, {
          children: [
            jsx('strong', { children: 'Status: ' }),
            status
          ]
        })
      }),

      error
        ? jsx('pre', {
            id: 'error',
            children: error
          })
        : null,

      jsxs('div', {
        children: [
          jsx('button', {
            onClick: initialize,
            disabled: isReady,
            children: isReady ? 'KeenASR Ready' : 'Initialize KeenASR'
          }),
          jsx('button', {
            onClick: startReading,
            disabled: !isReady || isListening || isStopping,
            children: 'Start Reading'
          }),
          jsx('button', {
            onClick: stopReading,
            disabled: !isListening || isStopping,
            children: 'Stop Reading'
          })
        ]
      }),

      jsxs('div', {
        class: 'audio-source',
        children: [
          jsx('strong', { children: 'Audio source: ' }),
          jsxs('select', {
            value: audioMode,
            disabled: isListening || isStopping,
            onChange: event => changeAudioMode(event.target.value),
            children: [
              jsx('option', { value: 'microphone', children: 'Live microphone' }),
              jsx('option', { value: 'recording', children: 'Recorded audio' })
            ]
          }),

          audioMode === 'recording'
            ? jsxs('div', {
                children: [
                  jsx('label', {
                    children: 'Upload a recording: '
                  }),
                  jsx('input', {
                    type: 'file',
                    accept: 'audio/*',
                    disabled: isListening || isStopping,
                    onChange: chooseRecordingFile
                  }),

                  bundledRecordings.length
                    ? jsxs('div', {
                        children: [
                          jsx('label', { children: 'or pick a bundled one: ' }),
                          jsxs('select', {
                            disabled: isListening || isStopping,
                            onChange: chooseBundledRecording,
                            children: [
                              jsx('option', { value: '', children: '— choose —' }),
                              ...bundledRecordings.map(item =>
                                jsx('option', {
                                  value: item.file,
                                  children: item.label || item.file
                                })
                              )
                            ]
                          })
                        ]
                      })
                    : null,

                  jsx('div', {
                    children: recordingInfo
                      ? `Loaded: ${recordingInfo}`
                      : 'No recording loaded yet.'
                  })
                ]
              })
            : null
        ]
      }),

      jsx('h2', { children: 'Reading passage' }),

      jsx('div', {
        class: 'passage',
        children: passage || 'Loading passage...'
      }),

      jsx('h2', { children: 'Live transcript' }),

      jsx('div', {
        class: 'log',
        children: transcript || 'Your recognized speech will appear here.'
      }),

      jsxs('p', {
        children: [
          jsx('strong', { children: 'Furthest aligned word index: ' }),
          String(furthestWord)
        ]
      }),

      jsx('h2', { children: 'Checkpoints' }),

      ...checkpointElements,

      jsx('h2', { children: 'Final alignment metrics' }),

      metrics
        ? jsx('div', {
            class: 'log',
            children: [
              metrics.accuracy == null
                ? 'Accuracy: unavailable'
                : `Accuracy: ${metrics.accuracy.toFixed(1)}%`,
              metrics.wordErrorRate == null
                ? 'Word error rate: unavailable'
                : `Word error rate: ${metrics.wordErrorRate}`
            ].join('\n')
          })
        : jsx('p', {
            children: 'Metrics appear after the final recognition result.'
          }),

      jsx('h2', { children: 'Event log' }),

      jsx('div', {
        class: 'log',
        children: events.length
          ? events.join('\n')
          : 'No events yet.'
      })
    ]
  });
}

render(jsx(App, {}), document.getElementById('app'));
