import React, { useEffect, useRef, useState } from 'react';

const endpoint = '/api/mapmap/wall-layout';
const perimeter = [0, 1, 3, 2];
const cornerNames = ['Top left', 'Top right', 'Bottom left', 'Bottom right'];
const arrowDirections = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };

function canvasFor(walls, outputSize) {
  if (outputSize) return { x: 0, y: 0, width: String(outputSize[0]), height: String(outputSize[1]) };
  const points = walls.flatMap(({ corners }) => corners);
  const x = Math.floor(Math.min(0, ...points.map(([left]) => left)));
  const y = Math.floor(Math.min(0, ...points.map(([, top]) => top)));
  const width = Math.ceil(Math.max(1280, ...points.map(([right]) => right - x + 64)));
  const height = Math.ceil(Math.max(720, ...points.map(([, bottom]) => bottom - y + 64)));
  return { x, y, width: String(width), height: String(height) };
}

function clampWallOffset(coordinates, origin, size, offset) {
  const firstEdge = origin - Math.min(...coordinates);
  const lastEdge = origin + size - Math.max(...coordinates);
  return Math.max(Math.min(firstEdge, lastEdge), Math.min(Math.max(firstEdge, lastEdge), Math.round(offset)));
}

export function WallEditor({ disabled, project, request }) {
  const dialog = useRef(null);
  const board = useRef(null);
  const drag = useRef(null);
  const preview = useRef({ timer: null, request: null, next: null, generation: 0, changed: false });
  const [saved, setSaved] = useState(null);
  const [history, setHistory] = useState({ past: [], draft: [], future: [] });
  const draft = history.draft;
  const [selected, setSelected] = useState(0);
  const [canvas, setCanvas] = useState(null);
  const [pending, setPending] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [skipped, setSkipped] = useState([]);
  const [previewing, setPreviewing] = useState(false);

  function cancelPreview() {
    const work = preview.current;
    clearTimeout(work.timer);
    work.timer = null;
    work.next = null;
    work.changed = false;
    work.generation += 1;
  }

  async function sendPreview() {
    const work = preview.current;
    work.timer = null;
    if (work.request || !work.next || !dialog.current?.open) return;
    const job = work.next;
    work.next = null;
    setPreviewing(true);
    setError('');
    setMessage('');
    try {
      work.request = request(`${endpoint}/preview`, { revision: job.revision, corners: job.corners });
      const result = await work.request;
      if (job.generation === work.generation) {
        setMessage('Preview updated on the projector.');
        setSkipped(result.skipped);
      }
    } catch (failure) {
      if (job.generation === work.generation) setError(failure.message);
    } finally {
      work.request = null;
      if (job.generation === work.generation) setPreviewing(false);
      if (work.next && !work.timer) sendPreview();
    }
  }

  function queuePreview(corners, delay = 250) {
    const work = preview.current;
    clearTimeout(work.timer);
    work.next = { revision: saved.revision, corners, generation: work.generation };
    work.timer = setTimeout(sendPreview, delay);
  }

  useEffect(() => {
    if (preview.current.changed && saved && dialog.current?.open) {
      preview.current.changed = false;
      queuePreview(draft);
    }
  }, [draft, saved]);

  useEffect(() => () => {
    cancelPreview();
  }, []);

  async function open() {
    cancelPreview();
    setPreviewing(false);
    setSaved(null);
    setError('');
    setMessage('');
    setSkipped([]);
    setSelected(0);
    setPending('loading');
    dialog.current.showModal();
    try {
      const layout = await request(endpoint);
      setSaved(layout);
      setHistory({ past: [], draft: layout.preview_corners ?? layout.walls.map(({ corners }) => corners), future: [] });
      setCanvas(canvasFor(layout.walls, layout.output_size));
    } catch (failure) {
      setError(failure.message);
    } finally {
      setPending('');
    }
  }

  async function save() {
    cancelPreview();
    setPreviewing(false);
    setPending('save');
    setError('');
    setMessage('');
    setSkipped([]);
    try {
      // Finish a preview before saving so old geometry cannot arrive afterward.
      await preview.current.request?.catch(() => {});
      const result = await request(`${endpoint}/save`, { revision: saved.revision, corners: draft });
      setSaved({ ...result, output_size: saved.output_size });
      setHistory((current) => ({ ...current, draft: result.walls.map(({ corners }) => corners) }));
      setMessage(result.live_applied
        ? `Layout saved to all scenes and applied in MapMap. ${result.updated} scenes updated.`
        : `Layout saved. ${result.updated} scenes updated. ${result.apply_error ? 'Retry Save and apply to finish the live update.' : 'Open MapMap when ready to project.'}`);
      setError(result.apply_error ?? '');
      setSkipped(result.skipped);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setPending('');
    }
  }

  function reset() {
    finishDrag();
    preview.current.changed = true;
    const restored = saved.walls.map(({ corners }) => corners);
    setHistory((current) => JSON.stringify(current.draft) === JSON.stringify(restored) ? current : {
      past: [...current.past, current.draft], draft: restored, future: [],
    });
    setCanvas(canvasFor(saved.walls, saved.output_size));
    setError('');
    setMessage('');
    setSkipped([]);
  }

  const width = Number(canvas?.width);
  const height = Number(canvas?.height);
  const validCanvas = width >= 240 && width <= 8192 && height >= 240 && height <= 8192;

  function moveCorner(index, x, y, remember = true) {
    const point = [
      Math.round(Math.max(canvas.x, Math.min(canvas.x + width, x))),
      Math.round(Math.max(canvas.y, Math.min(canvas.y + height, y))),
    ];
    preview.current.changed = true;
    setHistory((current) => {
      const previous = current.draft[selected][index];
      if (previous[0] === point[0] && previous[1] === point[1]) return current;
      const next = current.draft.map((wall, wallIndex) => wallIndex === selected
        ? wall.map((corner, cornerIndex) => cornerIndex === index ? point : corner) : wall);
      return { past: remember ? [...current.past, current.draft] : current.past, draft: next, future: [] };
    });
    setError('');
    setMessage('');
  }

  function boardPoint(event) {
    const bounds = board.current.getBoundingClientRect();
    return [
      canvas.x + (event.clientX - bounds.left) * width / bounds.width,
      canvas.y + (event.clientY - bounds.top) * height / bounds.height,
    ];
  }

  function beginDrag(event, index, corner) {
    if (event.button !== 0 || drag.current) return;
    const [x, y] = boardPoint(event);
    drag.current = { pointer: event.pointerId, index, before: draft, dx: corner[0] - x, dy: corner[1] - y };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function dragCorner(event) {
    const moving = drag.current;
    if (!moving || moving.pointer !== event.pointerId) return;
    const [x, y] = boardPoint(event);
    moveCorner(moving.index, x + moving.dx, y + moving.dy, false);
  }

  function beginWallDrag(event, wall) {
    if (event.button !== 0 || drag.current) return;
    setSelected(wall);
    drag.current = { pointer: event.pointerId, wall, before: draft, start: boardPoint(event) };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function dragWall(event) {
    const moving = drag.current;
    if (!moving || moving.pointer !== event.pointerId) return;
    const [x, y] = boardPoint(event);
    const corners = moving.before[moving.wall];
    const dx = clampWallOffset(corners.map(([left]) => left), canvas.x, width, x - moving.start[0]);
    const dy = clampWallOffset(corners.map(([, top]) => top), canvas.y, height, y - moving.start[1]);
    const translated = corners.map(([left, top]) => [left + dx, top + dy]);
    preview.current.changed = true;
    setHistory((current) => {
      if (JSON.stringify(current.draft[moving.wall]) === JSON.stringify(translated)) return current;
      return { ...current, draft: current.draft.map((wall, index) => index === moving.wall ? translated : wall), future: [] };
    });
    setError('');
    setMessage('');
  }

  function finishDrag(event) {
    const moving = drag.current;
    if (!moving || (event && moving.pointer !== event.pointerId)) return;
    drag.current = null;
    setHistory((current) => JSON.stringify(moving.before) === JSON.stringify(current.draft) ? current : {
      ...current, past: [...current.past, moving.before], future: [],
    });
  }

  function undo() {
    finishDrag();
    preview.current.changed = true;
    setHistory((current) => current.past.length ? {
      past: current.past.slice(0, -1), draft: current.past.at(-1), future: [current.draft, ...current.future],
    } : current);
    setError('');
    setMessage('');
  }

  function redo() {
    finishDrag();
    preview.current.changed = true;
    setHistory((current) => current.future.length ? {
      past: [...current.past, current.draft], draft: current.future[0], future: current.future.slice(1),
    } : current);
    setError('');
    setMessage('');
  }

  function historyShortcut(event) {
    if (disabled || pending || event.altKey || !(event.ctrlKey || event.metaKey)
      || event.target.closest('input, textarea, [contenteditable="true"]')) return;
    const key = event.key.toLowerCase();
    if (key !== 'z' && key !== 'y') return;
    event.preventDefault();
    if (key === 'y' || event.shiftKey) redo();
    else undo();
  }

  function nudge(event, index, [x, y]) {
    const direction = arrowDirections[event.key];
    if (!direction) return;
    event.preventDefault();
    const step = event.shiftKey ? 10 : 1;
    moveCorner(index, x + step * direction[0], y + step * direction[1], !event.repeat);
  }

  function percent([x, y]) {
    return [`${(x - canvas.x) / width * 100}%`, `${(y - canvas.y) / height * 100}%`];
  }

  return (
    <>
      <button type="button" disabled={disabled} onClick={open}>Edit wall layout</button>
      <dialog className="wall-editor" ref={dialog} aria-labelledby="wall-editor-title"
        onKeyDown={historyShortcut}
        onClose={() => { cancelPreview(); drag.current = null; setPreviewing(false); }}
        onCancel={(event) => { if (pending) event.preventDefault(); }}>
        <div className="wall-editor-header">
          <div>
            <h2 id="wall-editor-title">Edit wall layout</h2>
            <small>{project}</small>
          </div>
          <button type="button" disabled={Boolean(pending)} onClick={() => dialog.current.close()}>Close</button>
        </div>
        {pending === 'loading' && <p role="status">Loading the saved wall layout…</p>}
        {saved && (
          <fieldset disabled={disabled || Boolean(pending)}>
            <p>Drag inside a wall to move it. Drag a corner to reshape it, or use arrow keys to nudge a selected corner. The projector preview updates when you pause.</p>
            <div className="wall-selector" aria-label="Wall to edit">
              {saved.walls.map(({ name }, index) => (
                <button key={name} type="button" className={`wall-color-${index}`} aria-pressed={selected === index}
                  onClick={() => setSelected(index)}>{name}</button>
              ))}
            </div>
            <div className="wall-editor-actions">
              <button type="button" disabled={!history.past.length} onClick={undo} title="Ctrl+Z">Undo</button>
              <button type="button" disabled={!history.future.length} onClick={redo} title="Ctrl+Y or Ctrl+Shift+Z">Redo</button>
            </div>
            {validCanvas && (
              <div className="wall-board" ref={board} style={{ aspectRatio: width / height }}>
                {draft.map((corners, index) => {
                  const path = perimeter.map((corner) => percent(corners[corner]).join(' ')).join(', ');
                  return <button key={index} type="button" className={`wall-region wall-color-${index}`}
                    aria-label={`Select ${saved.walls[index].name}`} aria-pressed={index === selected}
                    onClick={() => setSelected(index)} data-selected={index === selected}
                    onPointerDown={(event) => beginWallDrag(event, index)} onPointerMove={dragWall}
                    onPointerUp={finishDrag} onPointerCancel={finishDrag} onLostPointerCapture={finishDrag}
                    style={{ clipPath: `polygon(${path})` }} />;
                })}
                {draft[selected].map((corner, index) => {
                  const [left, top] = percent(corner);
                  const label = `${saved.walls[selected].name} ${cornerNames[index].toLowerCase()} corner`;
                  return <button key={index} type="button" aria-label={label} title={`${label} (${corner.join(', ')})`}
                    className={`wall-handle wall-color-${selected}`} style={{ left, top }}
                    onPointerDown={(event) => beginDrag(event, index, corner)}
                    onPointerMove={dragCorner} onPointerUp={finishDrag} onPointerCancel={finishDrag}
                    onLostPointerCapture={finishDrag}
                    onKeyDown={(event) => nudge(event, index, corner)} />;
                })}
              </div>
            )}
            <div className="wall-canvas-size" aria-label="Editor canvas dimensions">
              {['width', 'height'].map((dimension) => (
                <label key={dimension}>
                  Editor {dimension}
                  <input type="number" min="240" max="8192" value={canvas[dimension]}
                    onChange={(event) => setCanvas({ ...canvas, [dimension]: event.target.value })} />
                </label>
              ))}
            </div>
            {saved.output_size && <small>MapMap output · {saved.output_size[0]} × {saved.output_size[1]}. Editor dimensions control the coordinate area shown here.</small>}
            {!validCanvas && <p role="status">Enter a canvas width and height from 240 to 8192 pixels.</p>}
            <small>Keep MapMap open to preview and save. Saving updates the shared wall layout for all compatible scenes.</small>
            <div className="wall-editor-actions">
              <button type="button" onClick={reset}>Reset draft</button>
              <button type="button" disabled={!validCanvas} onClick={() => queuePreview(draft, 0)}>
                {previewing ? 'Updating preview…' : 'Preview on projector'}
              </button>
              <button type="button" className="save-wall-layout" disabled={!validCanvas} onClick={save}>
                {pending === 'save' ? 'Saving layout…' : 'Save and apply to all scenes'}
              </button>
            </div>
          </fieldset>
        )}
        {error && <p className="wall-editor-error" role="alert">{error}</p>}
        {message && <p className="wall-editor-message" role="status">{message}</p>}
        {skipped.length > 0 && (
          <details>
            <summary>{skipped.length} scenes with a different mesh</summary>
            <ul>{skipped.map((name, index) => <li key={`${index}-${name}`}>{name}</li>)}</ul>
          </details>
        )}
      </dialog>
    </>
  );
}
