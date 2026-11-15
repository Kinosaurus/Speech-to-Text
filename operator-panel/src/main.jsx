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

function PassagePreview({ passage, fired, mapmap, transcript, partial, scores, cueStatus, listening }) {
  return (
    <section className="card preview" aria-labelledby="preview-title">
      <header className="section-header">
        <div>
          <h2 id="preview-title">{passage.title}</h2>
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
      <h3>Checkpoints</h3>
      <ol className="checkpoints">
        {passage.checkpoints.map(({ id, checkpoint_text, page, effect }) => {
          const didFire = fired.includes(id);
          const projects = mapmap && id === 'seed_found';
          return (
            <li key={id} className={didFire ? 'fired' : ''}>
              <span className="checkpoint-marker" aria-hidden="true">{didFire ? '✓' : ''}</span>
              <div>
                <div className="checkpoint-meta">Page {page} · {id}</div>
                <p>{checkpoint_text}</p>
                <small>{projects ? 'MapMap · Silver Seed video and soundtrack' : effect?.effect_id || 'Checkpoint match'}</small>
              </div>
              <div className="checkpoint-status">
                <span>{didFire ? 'Fired' : cueStatus[id] ?? 'Waiting'}</span>
                <span className="checkpoint-score" title="Alignment score. Firing also requires evidence for the checkpoint phrase.">
                  Match {scores[id] == null ? '—' : `${scores[id]}%`}
                </span>
              </div>
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
  const [pending, setPending] = useState(false);
  const [connectionError, setConnectionError] = useState('');
  const [actionError, setActionError] = useState('');
  const [connected, setConnected] = useState(false);
  const active = ['starting', 'listening', 'ending'].includes(session.phase);
  const selection = active ? session.settings || settings : settings;
  const model = catalog?.models.find((item) => item.id === selection.model);
  const passage = catalog?.passages.find((item) => item.id === selection.passage);
  const mapmap = catalog?.projection && selection.passage === 'sample';
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
  }

  async function act(action) {
    setPending(true);
    setActionError('');
    try {
      setSession(await request(`/api/session/${action}`, action === 'start' ? settings : {}));
    } catch (error) {
      setActionError(error.message);
    } finally {
      setPending(false);
    }
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
            <button type="button" className="end" disabled={!connected || !active || pending || session.phase === 'ending'} onClick={() => act('end')}>End experience</button>
            <button type="button" className="start" disabled={!connected || !model || !passage || pending || active} onClick={() => act('start')}>Start experience</button>
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
            <fieldset disabled={!catalog || pending || active}>
              <label className="field">
                <span>Passage</span>
                <select value={selection.passage} onChange={(event) => change('passage', event.target.value)}>
                  {catalog?.passages.map(({ id, title }) => <option key={id} value={id}>{title}</option>)}
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
            {passage && <p className="projection-note">{mapmap ? 'Projection configured for Sky Garden' : 'Checkpoint tracking and local sound effects'}</p>}
          </section>
          {passage && (
            <PassagePreview passage={passage} fired={fired} mapmap={mapmap}
              transcript={samePassage ? session.transcript : ''}
              partial={samePassage ? session.partial ?? [] : []}
              scores={samePassage ? session.scores ?? {} : {}}
              cueStatus={samePassage ? session.cue_status ?? {} : {}}
              listening={session.phase === 'listening'} />
          )}
        </div>
      </main>
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);
