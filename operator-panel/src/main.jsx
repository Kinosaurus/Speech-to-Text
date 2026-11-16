import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const defaults = { passage: 'sample', model: 'parakeet-nemo', microphone: 'default', hints: false, strength: 'medium', save: false };
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

function Preflight({ checks, projection, silverSeedTest, transition, disabled, checking, message, onCheck, onTest, onReset, onTransition }) {
  const mapmapState = checks?.mapmap.state ?? (projection ? '' : 'unconfigured');
  return (
    <section className="preflight" aria-labelledby="preflight-title">
      <div className="preflight-heading">
        <h3 id="preflight-title">Preflight</h3>
        <button type="button" disabled={disabled} onClick={onCheck}>{checking ? 'Checking…' : 'Check setup'}</button>
      </div>
      <dl className="preflight-checks" aria-live="polite">
        <div>
          <dt>Parakeet NeMo</dt>
          <dd>
            <strong className={checks?.nemo.state}>{checkLabels[checks?.nemo.state] ?? 'Unchecked'}</strong>
            {checks && <small>{checks.nemo.detail}</small>}
          </dd>
        </div>
        <div>
          <dt>MapMap OSC</dt>
          <dd>
            <strong className={mapmapState}>
              {mapmapState === 'ready' ? 'Listener found' : checkLabels[mapmapState] ?? 'Unchecked'}
            </strong>
            {checks && <small>{checks.mapmap.detail}</small>}
          </dd>
        </div>
      </dl>
      <div className="preflight-controls">
        <button type="button" disabled={disabled || !silverSeedTest} onClick={onTest}>Test Silver Seed</button>
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
  cueOptions, mapmapProject, canEditCues, cueEditingDisabled, assignmentMessage, onAssignCue }) {
  const [editingCues, setEditingCues] = useState(false);
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
        {passage.checkpoints.map(({ id, checkpoint_text, page, playback, mapmap_cue: assignedCue }) => {
          const didFire = fired.includes(id);
          const isCurrent = listening && id === readingCheckpoint;
          const cueAvailable = cueOptions.some(({ id: cueId }) => cueId === assignedCue);
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
  const [assignmentMessage, setAssignmentMessage] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [actionError, setActionError] = useState('');
  const [connected, setConnected] = useState(false);
  const active = ['starting', 'listening', 'ending'].includes(session.phase);
  const busy = Boolean(pending);
  const selection = active ? session.settings || settings : settings;
  const model = catalog?.models.find((item) => item.id === selection.model);
  const passage = catalog?.passages.find((item) => item.id === selection.passage);
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
    if (key === 'passage') setAssignmentMessage('');
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
    act('/api/preflight', {}, setChecks);
  }

  function manualCue(action) {
    act(`/api/mapmap/${action}`, {}, ({ message }) => setProjectionMessage(message));
  }

  function assignCue(checkpoint, cue) {
    act('/api/mapmap/assignment', { passage: selection.passage, checkpoint, cue }, (updatedCatalog) => {
      setCatalog(updatedCatalog);
      setAssignmentMessage(cue ? 'MapMap cue assigned.' : 'MapMap cue removed.');
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
            <button type="button" className="start" disabled={!connected || !model || !passage || busy || active} onClick={() => act('/api/session/start', settings, setSession)}>Start experience</button>
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
                <Toggle label="Reading hints" description={model?.hints ? 'Give the model upcoming phrases from the passage.' : 'The selected model does not support reading hints.'}
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
                  <small>{selection.model === 'parakeet-nemo'
                    ? 'Changes how many phrases are included. Boost weight is set on the NeMo server.'
                    : 'Changes how much upcoming passage context is included.'}</small>
                </fieldset>
              </div>
              <div className="setting-block">
                <Toggle label="Save recording" description="Keep a local WAV. Transcripts are always stored locally."
                  checked={selection.save} onChange={(event) => change('save', event.target.checked)} />
              </div>
            </fieldset>
            <Preflight checks={checks} projection={catalog?.projection} silverSeedTest={catalog?.silver_seed_test ?? catalog?.projection}
              transition={catalog?.mapmap_transition} onTransition={changeTransition}
              disabled={!connected || busy || active} checking={pending === '/api/preflight'}
              message={projectionMessage} onCheck={checkSetup}
              onTest={() => manualCue('test')} onReset={() => manualCue('reset')} />
          </section>
          {passage && (
            <PassagePreview passage={passage} fired={fired}
              transcript={samePassage ? session.transcript : ''}
              partial={samePassage ? session.partial ?? [] : []}
              scores={samePassage ? session.scores ?? {} : {}}
              cueStatus={samePassage ? session.cue_status ?? {} : {}}
              matchEvidence={samePassage ? session.match_evidence ?? {} : {}}
              readingCheckpoint={samePassage ? session.reading_checkpoint : null}
              listening={session.phase === 'listening'}
              cueOptions={catalog?.mapmap_cues ?? []} mapmapProject={catalog?.mapmap_project}
              canEditCues={!active && Boolean(catalog?.mapmap_project)} cueEditingDisabled={!connected || busy}
              assignmentMessage={assignmentMessage} onAssignCue={assignCue} />
          )}
        </div>
      </main>
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);
