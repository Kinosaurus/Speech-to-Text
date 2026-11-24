import React, { useCallback, useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { createRoot } from 'react-dom/client';
import { WallEditor } from './wall-editor.jsx';
import './styles.css';

const defaults = { passage: 'sample', model: 'nemotron', microphone: 'default', hints: true, strength: 'medium', save: false };
const phases = {
  idle: 'Ready to start',
  starting: 'Connecting',
  listening: 'Listening',
  ending: 'Ending session',
  ended: 'Session ended',
  error: 'Session interrupted',
};
const checkLabels = {
  ready: 'Ready',
  error: 'Check failed',
  unknown: 'Unverified',
  unconfigured: 'Not configured',
  checking: 'Checking…',
  starting: 'Starting…',
  restarting: 'Restarting…',
};
const wordLabels = {
  exact: 'Exact match',
  spelling: 'Similar spelling or word form',
  sound: 'Similar sound',
  split: 'Split word',
  article_waived: 'Forgiven article',
  omitted: 'Missing word · no credit',
  unmatched: 'No word credit',
};
const playbackLabels = {
  mapmap: 'MapMap projection',
  local_sound: 'Local sound',
  tracking: 'Tracking only',
};

async function request(path, body, signal) {
  const response = await fetch(path, {
    signal,
    ...(body && {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  });
  if (!response.headers.get('Content-Type')?.includes('application/json')) {
    throw new Error('The local panel server did not respond. Check that it is running.');
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The request failed.');
  return data;
}

function Toggle({ label, description, checked, onChange, disabled }) {
  return (
    <label className="toggle">
      <span>
        <strong>{label}</strong>
        <small>{description}</small>
      </span>
      <input type="checkbox" role="switch" checked={checked} onChange={onChange} disabled={disabled} />
    </label>
  );
}

function OutputLayout({ disabled, onLayout, wallProject }) {
  const [width, setWidth] = useState('1024');
  const [height, setHeight] = useState('768');
  function fit(event) {
    event.preventDefault();
    onLayout({ mode: 'fit', width: Number(width), height: Number(height) });
  }
  return (
    <details className="output-layout">
      <summary>Output layout</summary>
      <div className="preflight-controls output-actions">
        <button type="button" disabled={disabled} onClick={() => onLayout({ mode: 'auto' })}>Fit output</button>
        <button type="button" disabled={disabled} onClick={() => onLayout({ mode: 'original' })}>Restore original</button>
        {wallProject && <WallEditor disabled={disabled} project={wallProject} request={request} />}
      </div>
      <details className="manual-layout">
        <summary>Manual dimensions</summary>
        <form onSubmit={fit}>
          <fieldset disabled={disabled}>
            <div className="output-dimensions">
              <label>Width (px)<input type="number" min="240" max="8192" required value={width} onChange={(event) => setWidth(event.target.value)} /></label>
              <label>Height (px)<input type="number" min="240" max="8192" required value={height} onChange={(event) => setHeight(event.target.value)} /></label>
            </div>
            <button type="submit" disabled={disabled}>Fit manual size</button>
          </fieldset>
        </form>
      </details>
    </details>
  );
}

function Preflight({ checks, projection, silverSeedTest, transition, cues, layout, wallProject, disabled, checking, message,
  sceneDirectory, sceneUpdate, sceneAction, onSceneAction, onCheck, onTest, onReset, onTransition, onPreview, onLayout,
  recognition, recognitionLabel, serverDisabled, reading, onServer, mapmap, onOpenMapMap }) {
  const showSilverSeedTest = silverSeedTest && cues.length <= 1;
  const mapmapState = mapmap?.state ?? checks?.mapmap.state ?? (projection ? '' : 'unconfigured');
  return (
    <section className="preflight" aria-labelledby="preflight-title">
      <div className="preflight-heading">
        <h3 id="preflight-title">Preflight</h3>
        <button type="button" disabled={disabled} onClick={onCheck}>{checking ? 'Checking…' : 'Check setup'}</button>
      </div>
      <dl className="preflight-checks" aria-live="polite">
        <div>
          <dt>{recognitionLabel}</dt>
          <dd>
            <strong className={recognition?.state ?? checks?.nemo.state}>
              {checkLabels[recognition?.state ?? checks?.nemo.state] ?? 'Unchecked'}
            </strong>
            <small>{recognition?.detail ?? checks?.nemo.detail}</small>
          </dd>
        </div>
        <div>
          <dt>MapMap OSC</dt>
          <dd>
            <strong className={mapmapState}>
              {mapmapState === 'ready' ? 'Running · OSC connected' : mapmapState === 'starting' ? 'Opening…' : checkLabels[mapmapState] ?? 'Unchecked'}
            </strong>
            <small>{mapmap?.detail ?? checks?.mapmap.detail}</small>
          </dd>
        </div>
      </dl>
      {mapmap?.managed && (
        <div className="preflight-controls">
          <button type="button" disabled={disabled || mapmap.busy || mapmap.state === 'ready'} onClick={onOpenMapMap}>
            {mapmap.state === 'starting' ? 'Opening MapMap…' : 'Open MapMap'}
          </button>
        </div>
      )}
      {recognition?.managed && (
        <div className="recognition-controls" aria-live="polite">
          <div className="preflight-controls">
            <button type="button" disabled={serverDisabled || reading || recognition.state === 'ready'}
              onClick={() => onServer('start')}>Start recognition server</button>
            <button type="button" disabled={serverDisabled}
              onClick={() => onServer('restart')}>Restart recognition server</button>
          </div>
          {reading && <small>Restart ends the current reading session.</small>}
          {recognition.state === 'error' && <small>Server log · {recognition.log}</small>}
        </div>
      )}
      {sceneDirectory && (
        <fieldset className="scene-library" disabled={disabled}>
          <legend>Scene library</legend>
          <p>Drop MP4, MOV, WebM, PNG, or JPEG files in this folder. Save and close MapMap before importing.</p>
          <code>{sceneDirectory}</code>
          <div className="preflight-controls">
            <button type="button" onClick={() => onSceneAction('import')}>
              {sceneAction === 'import' ? 'Importing…' : 'Import scenes'}
            </button>
            <button type="button" onClick={() => onSceneAction('apply-layout')}>
              {sceneAction === 'apply-layout' ? 'Applying layout…' : 'Apply wall layout to all scenes'}
            </button>
          </div>
          {sceneUpdate && (
            <p role="status">
              {sceneUpdate.imported
                ? (sceneUpdate.imported.length ? `Imported ${sceneUpdate.imported.length}.` : 'No new scenes imported.')
                : `Wall layout applied to ${sceneUpdate.updated} scenes.`}
              {sceneUpdate.existing > 0 && ` ${sceneUpdate.existing} already in the project.`}
              {(sceneUpdate.imported?.length > 0 || sceneUpdate.updated > 0)
                && ' Open the updated project in MapMap before projecting.'}
            </p>
          )}
          {sceneUpdate?.skipped.length > 0 && (
            <details>
              <summary>{sceneUpdate.skipped.length} skipped</summary>
              <ul>{sceneUpdate.skipped.map((issue, index) => <li key={`${index}-${issue}`}>{issue}</li>)}</ul>
            </details>
          )}
        </fieldset>
      )}
      {!showSilverSeedTest && cues.length > 0 && (
        <fieldset className="scene-preview" disabled={disabled}>
          <legend>Preview scenes</legend>
          <div className="scene-preview-buttons">
            {cues.map(({ id, title }) => (
              <button key={id} type="button" onClick={() => onPreview(id)}>Show {title}</button>
            ))}
          </div>
        </fieldset>
      )}
      <div className="preflight-controls">
        {showSilverSeedTest && <button type="button" disabled={disabled} onClick={onTest}>Test Silver Seed</button>}
        <button type="button" disabled={disabled || !projection} onClick={onReset}>Reset to grid</button>
      </div>
      {transition && (
        <label className="field mapmap-transition">
          <span>Scene transition</span>
          <select disabled={disabled} value={transition.fade_ms} onChange={(event) => onTransition(Number(event.target.value))}>
            {transition.options_ms.map((ms) => <option key={ms} value={ms}>{ms ? `Crossfade · ${ms} ms` : 'Cut'}</option>)}
          </select>
        </label>
      )}
      {layout && <OutputLayout disabled={disabled} onLayout={onLayout} wallProject={wallProject} />}
      {message && <p className="preflight-message" role="status">{message}</p>}
    </section>
  );
}

function highlightTranscript(text, partial) {
  if (!partial.length) return text;
  const characters = Array.from(text);
  const parts = [];
  let cursor = 0;
  for (const { start, end, expected, credit } of [...partial].sort((a, b) => a.start - b.start)) {
    if (start < cursor || end <= start || end > characters.length) continue;
    parts.push(characters.slice(cursor, start).join(''));
    const heard = characters.slice(start, end).join('');
    const detail = credit == null
      ? `Approximate match for “${expected}”`
      : `${Math.round(credit * 100)}% word credit toward “${expected}”`;
    parts.push(<mark key={start} title={detail} aria-label={`${heard}. ${detail}`}>{heard}</mark>);
    cursor = end;
  }
  parts.push(characters.slice(cursor).join(''));
  return parts;
}

function LiveTranscript({ text, partial, listening }) {
  const box = useRef(null);
  useEffect(() => {
    box.current.scrollTop = box.current.scrollHeight;
  }, [text]);

  return (
    <section className="live-transcript" aria-labelledby="transcript-title">
      <h3 id="transcript-title">Live transcript</h3>
      <div className="transcript-text" ref={box} tabIndex={0} aria-labelledby="transcript-title">
        {text ? highlightTranscript(text, partial) : <span>{listening ? 'Waiting for speech…' : 'Speech appears here during a session.'}</span>}
      </div>
      {partial.length > 0 && <small className="transcript-key">Highlighted words received approximate match credit.</small>}
    </section>
  );
}

function MatchWords({ title, words }) {
  return (
    <table className="match-words">
      <caption>{title}</caption>
      <thead><tr><th scope="col">Book</th><th scope="col">Recognized</th><th scope="col">How it counted</th></tr></thead>
      <tbody>
        {words.map(({ expected, heard, kind, credit }, index) => (
          <tr key={index}>
            <td>{expected}</td>
            <td>{heard ?? '—'}</td>
            <td>
              <span className={`word-badge word-${kind}`}>{wordLabels[kind]}</span>
              {credit != null && credit < 1 && <span className="word-credit">{Math.round(credit * 100)}% word credit</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CheckpointEvidence({ evidence, autoOpen }) {
  const { words, cue_words: cueWords, confirmations, required, reason } = evidence;
  const primary = cueWords.length ? cueWords : words;
  const counts = new Map();
  for (const { kind } of primary) counts.set(kind, (counts.get(kind) ?? 0) + 1);
  const alignmentDiffers = cueWords.length && words.length && (
    words.length !== cueWords.length || words.some((word, index) => (
      word.expected !== cueWords[index].expected || word.heard !== cueWords[index].heard || word.kind !== cueWords[index].kind
    ))
  );

  return (
    <details className="checkpoint-evidence" open={autoOpen}>
      <summary>
        Match evidence
        {counts.size > 0 && (
          <span className="evidence-counts">
            {[...counts].map(([kind, count]) => (
              <span key={kind} className={`word-badge word-${kind}`}>{wordLabels[kind]} ({count})</span>
            ))}
          </span>
        )}
      </summary>
      <p>{confirmations} of {required} required alignment confirmations</p>
      {reason && <p className="evidence-reason">{reason}</p>}
      {primary.length > 0 && <MatchWords title={cueWords.length ? 'Cue evidence' : 'Latest reading alignment'} words={primary} />}
      {Boolean(alignmentDiffers) && (
        <>
          <p>The reading alignment gives the match score. The cue evidence shows what cleared the effect check.</p>
          <MatchWords title="Reading alignment" words={words} />
        </>
      )}
    </details>
  );
}

function passagePlaybackLabel({ checkpoints }) {
  const kinds = new Set(checkpoints.map(({ playback }) => playback?.kind));
  if (kinds.has(undefined)) return '';
  const localSound = kinds.has('local_sound') || checkpoints.some(({ playback }) => playback.local_sound);
  if (kinds.has('mapmap')) return localSound ? 'MapMap + local sounds' : 'MapMap projection';
  return localSound ? 'Local sounds only' : 'Tracking only';
}

function PassagePreview({ passage, fired, transcript, partial, scores, cueStatus, matchEvidence, readingCheckpoint, listening,
  cueOptions, mapmapProject, canEditCues, cueEditingDisabled, assignmentMessage, onAssignCue, previewDisabled }) {
  const [editingCues, setEditingCues] = useState(false);
  const [currentPreview, setCurrentPreview] = useState(null);
  const previewPlayer = useRef(null);
  const attachPreviewPlayer = useCallback((video) => {
    previewPlayer.current = video;
    return () => {
      video.pause();
      previewPlayer.current = null;
    };
  }, []);
  useEffect(() => {
    if (previewDisabled) setCurrentPreview(null);
  }, [previewDisabled]);

  function togglePreview(url) {
    if (currentPreview === url) {
      setCurrentPreview(null);
      return;
    }
    // Keep play() inside the button's click so browser audio can start.
    flushSync(() => setCurrentPreview(url));
    previewPlayer.current?.play().catch(() => {
      // The player's controls are still available if browser settings block playback.
    });
  }

  const showCueEditors = canEditCues && editingCues;
  const playbackLabel = passagePlaybackLabel(passage);
  const evidenceCheckpoint = matchEvidence[readingCheckpoint] ? readingCheckpoint
    : passage.checkpoints.findLast(({ id }) => matchEvidence[id] && (
      fired.includes(id) || ['Checking ending', 'Cue withheld'].includes(cueStatus[id])
    ))?.id;
  return (
    <section className="card preview" aria-labelledby="preview-title">
      <header className="section-header">
        <div>
          <h2 id="preview-title">{passage.title}</h2>
          {playbackLabel && <small className="passage-playback">{playbackLabel}</small>}
        </div>
        <span className="count">{fired.length} / {passage.checkpoints.length} fired</span>
      </header>
      <div className="reading-columns">
        <section aria-labelledby="passage-title">
          <h3 id="passage-title">Reading passage</h3>
          <div className="passage" tabIndex={0} aria-labelledby="passage-title">
            {passage.pages.length
              ? passage.pages.map(({ page, text }) => (
                <div key={page}><span className="page-label">Page {page}</span><p>{text}</p></div>
              ))
              : <p>Only checkpoint phrases are available for this passage.</p>}
          </div>
        </section>
        <LiveTranscript text={transcript} partial={partial} listening={listening} />
      </div>
      <div className="checkpoint-heading">
        <h3>Checkpoints</h3>
        {canEditCues && (
          <button type="button" disabled={cueEditingDisabled} aria-expanded={showCueEditors}
            onClick={() => setEditingCues(!editingCues)}>{showCueEditors ? 'Done editing cues' : 'Edit MapMap cues'}</button>
        )}
      </div>
      {showCueEditors && <small className="cue-editor-note">Cues from {mapmapProject}. Changes save locally as you make them.</small>}
      {assignmentMessage && <p className="cue-editor-note" role="status">{assignmentMessage}</p>}
      <ol className="checkpoints">
        {passage.checkpoints.map(({ id, checkpoint_text, page, playback, preview_url: previewUrl, mapmap_cue: assignedCue }) => {
          const didFire = fired.includes(id);
          const isCurrent = listening && id === readingCheckpoint;
          const cueAvailable = cueOptions.some(({ id: cueId }) => cueId === assignedCue);
          const previewOpen = !previewDisabled && currentPreview === previewUrl && Boolean(previewUrl);
          return (
            <li key={id} className={isCurrent ? 'current' : didFire ? 'fired' : ''} aria-current={isCurrent ? 'step' : undefined}>
              <span className="checkpoint-marker" aria-hidden="true">{didFire ? '✓' : ''}</span>
              <div>
                <div className="checkpoint-meta">Page {page} · {id}</div>
                <p>{checkpoint_text}</p>
                {playback && (
                  <div className="checkpoint-playback">
                    <span className={`playback-badge playback-${playback.kind}`}>{playbackLabels[playback.kind]}</span>
                    {playback.local_sound && <span className="playback-badge playback-local_sound">Local sound</span>}
                    {playback.detail && <small>{playback.detail}</small>}
                  </div>
                )}
                {assignedCue && !cueAvailable && <small className="cue-unavailable">The saved MapMap cue is unavailable in this project.</small>}
                {previewUrl && (
                  <button type="button" className="checkpoint-preview-button" aria-expanded={previewOpen}
                    aria-label={`${previewOpen ? 'Close preview' : 'Test cue'} for page ${page}, ${checkpoint_text}`}
                    disabled={previewDisabled} onClick={() => togglePreview(previewUrl)}>
                    {previewOpen ? 'Close preview' : 'Test cue'}
                  </button>
                )}
                {showCueEditors && (
                  <label className="cue-editor">
                    <span>MapMap cue</span>
                    <select aria-label={`MapMap cue for ${id}`} value={assignedCue ?? ''}
                      disabled={cueEditingDisabled} onChange={(event) => onAssignCue(String(id), event.target.value || null)}>
                      <option value="">No MapMap cue</option>
                      {assignedCue && !cueAvailable && <option value={assignedCue} disabled>Unavailable cue</option>}
                      {cueOptions.map(({ id: cueId, title }) => <option key={cueId} value={cueId}>{title}</option>)}
                    </select>
                  </label>
                )}
              </div>
              <div className="checkpoint-status">
                <span>{didFire ? 'Fired' : cueStatus[id] ?? (isCurrent ? 'Reading now' : 'Waiting')}</span>
                <span className="checkpoint-score" title="Alignment score. Firing also requires evidence for the checkpoint phrase.">
                  Match {scores[id] == null ? '—' : `${scores[id]}%`}
                </span>
              </div>
              {previewOpen && (
                <video className="checkpoint-preview-video" ref={attachPreviewPlayer} src={previewUrl}
                  aria-label={`Cue preview for page ${page}`} controls playsInline preload="none" />
              )}
              {matchEvidence[id] && <CheckpointEvidence evidence={matchEvidence[id]} autoOpen={id === evidenceCheckpoint} />}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function App() {
  const [catalog, setCatalog] = useState(null);
  const [session, setSession] = useState({ phase: 'idle', fired: [] });
  const [settings, setSettings] = useState(defaults);
  const [pending, setPending] = useState('');
  const [checks, setChecks] = useState(null);
  const [projectionMessage, setProjectionMessage] = useState('');
  const [sceneUpdate, setSceneUpdate] = useState(null);
  const [assignmentMessage, setAssignmentMessage] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [actionError, setActionError] = useState('');
  const [connected, setConnected] = useState(false);
  const active = ['starting', 'listening', 'ending'].includes(session.phase);
  const busy = Boolean(pending) || session.mapmap?.state === 'starting';
  const selection = active ? session.settings || settings : settings;
  const model = catalog?.models.find((item) => item.id === selection.model);
  const serverBusy = Boolean(session.recognition?.busy);
  const recognitionBackend = model?.managed ? selection.model : catalog?.default_model ?? defaults.model;
  const recognition = session.recognition && session.recognition.backend !== recognitionBackend
    ? { ...session.recognition, state: serverBusy ? session.recognition.state : 'unconfigured',
        detail: serverBusy ? session.recognition.detail : 'Start the selected recognition model.' }
    : session.recognition;
  const waitingForNemo = model?.managed && (!recognition || recognition.state !== 'ready' || serverBusy);
  const passage = catalog?.passages.find((item) => item.id === selection.passage);
  const assignedScenes = new Set(passage?.checkpoints.map((checkpoint) => checkpoint.mapmap_cue));
  const previewScenes = (catalog?.mapmap_cues ?? []).filter(({ id }) => !catalog?.mapmap_story || assignedScenes.has(id));
  const samePassage = session.settings?.passage === selection.passage;
  const fired = samePassage ? session.fired : [];

  useEffect(() => {
    const controller = new AbortController();
    let loaded = false;
    let timer;
    async function poll() {
      try {
        if (!loaded) {
          const data = await request('/api/catalog', undefined, controller.signal);
          setCatalog(data);
          setSettings((current) => ({
            ...current,
            model: data.default_model ?? current.model,
            passage: data.mapmap_story || current.passage,
          }));
          loaded = true;
        }
        setSession(await request('/api/session', undefined, controller.signal));
        setConnected(true);
        setConnectionError('');
      } catch (error) {
        if (!controller.signal.aborted) {
          setConnected(false);
          setConnectionError(error.message);
        }
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(poll, 500);
      }
    }
    poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, []);

  function change(key, value) {
    setSettings((current) => ({ ...current, [key]: value }));
    setActionError('');
    if (key === 'passage') {
      setAssignmentMessage('');
      if (catalog?.mapmap_story) {
        act('/api/mapmap/story', { passage: value }, ({ message }) => setProjectionMessage(message));
      }
    }
  }

  async function act(path, body, onSuccess) {
    setPending(path);
    setActionError('');
    setProjectionMessage('');
    setAssignmentMessage('');
    try {
      onSuccess(await request(path, body));
    } catch (error) {
      setActionError(error.message);
    } finally {
      setPending('');
    }
  }

  function checkSetup() {
    setChecks(null);
    act('/api/preflight', { model: recognitionBackend }, setChecks);
  }

  function manualCue(action, body = {}) {
    act(`/api/mapmap/${action}`, body, ({ message }) => setProjectionMessage(message));
  }

  function assignCue(checkpoint, cue) {
    act('/api/mapmap/assignment', { passage: selection.passage, checkpoint, cue }, (updatedCatalog) => {
      setCatalog(updatedCatalog);
      setAssignmentMessage(cue ? 'MapMap cue assigned.' : 'MapMap cue removed.');
    });
  }

  function updateScenes(action) {
    setSceneUpdate(null);
    act(`/api/mapmap/scenes/${action}`, {}, ({ catalog: updatedCatalog, ...result }) => {
      setCatalog(updatedCatalog);
      setSceneUpdate(result);
      setChecks(null);
    });
  }

  function changeTransition(fadeMs) {
    act('/api/mapmap/transition', { fade_ms: fadeMs }, (updatedCatalog) => {
      setCatalog(updatedCatalog);
      setProjectionMessage('Scene transition saved.');
    });
  }

  return (
    <>
      <header className="top">
        <div className="top-inner">
          <div>
            <p className="eyebrow">Operator panel</p>
            <h1>Reading Pod</h1>
          </div>
          <div className="session-controls">
            <span role="status" className={`phase ${connected ? session.phase : 'offline'}`}>
              <span aria-hidden="true" />
              {connected ? phases[session.phase] : connectionError ? 'Disconnected' : 'Connecting to panel'}
            </span>
            <button type="button" className="end" disabled={!connected || !active || busy || session.phase === 'ending'} onClick={() => act('/api/session/end', {}, setSession)}>End experience</button>
            <button type="button" className="start" disabled={!connected || !model || !passage || busy || active || waitingForNemo} onClick={() => act('/api/session/start', settings, setSession)}>Start experience</button>
          </div>
        </div>
      </header>
      <main>
        {(connectionError || actionError || session.message) && (
          <p role="alert" className="error-message">{connectionError || actionError || session.message}</p>
        )}
        <div className="workspace">
          <section className="card settings" aria-labelledby="settings-title">
            <h2 id="settings-title">Session setup</h2>
            <fieldset disabled={!catalog || busy || active}>
              <label className="field">
                <span>Passage</span>
                <select value={selection.passage} onChange={(event) => change('passage', event.target.value)}>
                  {catalog?.passages.map((item) => {
                    const playback = passagePlaybackLabel(item);
                    return <option key={item.id} value={item.id}>{item.title}{playback && ` · ${playback}`}</option>;
                  })}
                </select>
                {pending === '/api/mapmap/story' && <small role="status">Loading the story’s projection scenes…</small>}
              </label>
              <label className="field">
                <span>Speech model</span>
                <select value={selection.model} onChange={(event) => change('model', event.target.value)}>
                  {catalog?.models.map(({ id, label }) => <option key={id} value={id}>{label}</option>)}
                </select>
                {model && <small>Local recognition server · port {model.port}</small>}
              </label>
              <label className="field">
                <span>Microphone</span>
                <select value={selection.microphone ?? 'default'} onChange={(event) => change('microphone', event.target.value)}>
                  <option value="default">System default</option>
                  {catalog?.microphones?.map(({ id, label }) => <option key={id} value={id}>{label}</option>)}
                </select>
                {!catalog?.microphones?.length && catalog && <small>Refresh the page after connecting a microphone.</small>}
              </label>
              {session.microphone && (
                <p className="microphone-status" role="status">
                  <strong>{active ? 'Input in use' : 'Last input used'}</strong>
                  <small>{session.microphone}</small>
                </p>
              )}
              <div className="setting-block">
                <Toggle label="Reading hints" description={model?.hints ? 'Help recognition with upcoming checkpoint phrases. The tracker follows the full story.' : 'The selected model does not support reading hints.'}
                  checked={Boolean(model?.hints && selection.hints)} disabled={!model?.hints}
                  onChange={(event) => change('hints', event.target.checked)} />
                <fieldset className="strength" disabled={!model?.hints || !selection.hints}>
                  <legend>Hint strength</legend>
                  <div className="segments">
                    {['low', 'medium', 'high'].map((level) => (
                      <label key={level}>
                        <input type="radio" name="strength" value={level} checked={selection.strength === level}
                          onChange={() => change('strength', level)} />
                        <span>{level}</span>
                      </label>
                    ))}
                  </div>
                  <small>{model?.managed
                    ? 'Medium includes the current cue and up to two ahead. An unfinished cue stays included while its ending is checked.'
                    : 'Changes how much upcoming passage context is included.'}</small>
                </fieldset>
              </div>
              <div className="setting-block">
                <Toggle label="Save recording" description="Keep a local WAV. Transcripts are always stored locally."
                  checked={selection.save} onChange={(event) => change('save', event.target.checked)} />
              </div>
            </fieldset>
            <Preflight checks={checks} projection={catalog?.projection}
              mapmap={session.mapmap}
              onOpenMapMap={() => act('/api/mapmap/open', {}, (status) => {
                setSession((current) => ({ ...current, mapmap: status }));
              })}
              recognition={recognition} recognitionLabel={catalog?.models.find((item) => item.id === recognitionBackend)?.label} reading={active} serverDisabled={!connected || busy || serverBusy}
              onServer={(action) => act(`/api/recognition/${action}`, { model: recognitionBackend }, (status) => {
                setSession((current) => ({ ...current, recognition: status }));
              })}
              silverSeedTest={!catalog?.mapmap_story && (catalog?.silver_seed_test ?? catalog?.projection)}
              transition={catalog?.mapmap_transition} onTransition={changeTransition} cues={previewScenes}
              sceneDirectory={catalog?.mapmap_scene_directory} sceneUpdate={sceneUpdate} onSceneAction={updateScenes}
              sceneAction={pending.startsWith('/api/mapmap/scenes/') ? pending.split('/').at(-1) : ''}
              layout={catalog?.mapmap_layout} wallProject={catalog?.mapmap_scene_directory && catalog.mapmap_project}
              onLayout={(settings) => manualCue('layout', settings)}
              disabled={!connected || busy || active} checking={pending === '/api/preflight'}
              message={projectionMessage} onCheck={checkSetup}
              onTest={() => manualCue('test')} onReset={() => manualCue('reset')}
              onPreview={(cue) => manualCue('preview', { cue })} />
          </section>
          {passage && (
            <PassagePreview key={passage.id} passage={passage} fired={fired}
              transcript={samePassage ? session.transcript : ''}
              partial={samePassage ? session.partial ?? [] : []}
              scores={samePassage ? session.scores ?? {} : {}}
              cueStatus={samePassage ? session.cue_status ?? {} : {}}
              matchEvidence={samePassage ? session.match_evidence ?? {} : {}}
              readingCheckpoint={samePassage ? session.reading_checkpoint : null}
              listening={session.phase === 'listening'}
              cueOptions={catalog?.mapmap_cues ?? []} mapmapProject={catalog?.mapmap_project}
              canEditCues={!active && Boolean(catalog?.mapmap_project)} cueEditingDisabled={!connected || busy}
              assignmentMessage={assignmentMessage} onAssignCue={assignCue} previewDisabled={active || pending === '/api/session/start'} />
          )}
        </div>
      </main>
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);
