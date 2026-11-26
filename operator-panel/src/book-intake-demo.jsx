import React, { useState } from 'react';
import gardenArtwork from '../../picture-gallery/sky-garden--silver-seed-at-the-gate.png';
import './book-intake-demo.css';

const stages = [
  { id: 'scans', name: 'Scan intake', owner: 'NLB staff', status: 'Scans verified' },
  { id: 'processing', name: 'School processing', owner: 'School team', status: 'Draft ready' },
  { id: 'review', name: 'Review & publish', owner: 'NLB staff', status: 'Awaiting approval' },
];

const processingSteps = [
  ['Pick up the job', 'The school worker checks the API, downloads the verified scans, and queues the job locally.'],
  ['Extract the passage', 'EasyOCR reads the pages in order and combines the text into one passage.'],
  ['Suggest checkpoints and effects', 'Qwen via Ollama uses the page text and illustrations to suggest cue phrases, sounds, and lighting.'],
  ['Send the draft for review', 'The worker uploads the passage and checkpoint JSON to private S3. The API checks both files and removes the staged scans.'],
];

function ScanIntake() {
  return (
    <>
      <h3>Page scans</h3>
      <p className="intake-description">Confirm the page order before the school worker picks up the job.</p>
      <ol className="intake-list">
        {['Page 01', 'Page 02', 'Page 03', 'Page 04'].map((page, index) => (
          <li key={page}><strong>{page}</strong><span>sky-garden-0{index + 1}.jpg</span></li>
        ))}
      </ol>
      <p className="intake-note">4 scans staged in private S3. The API verified all expected files and marked the job ready.</p>
    </>
  );
}

function SchoolProcessing() {
  return (
    <>
      <h3>School server job</h3>
      <p className="intake-description">The school GPU server prepares a draft for NLB review.</p>
      <ol className="intake-list">
        {processingSteps.map(([title, detail]) => (
          <li key={title}><strong>{title}</strong><span>{detail}</span></li>
        ))}
      </ol>
    </>
  );
}

function DraftReview() {
  return (
    <>
      <h3>Review the draft</h3>
      <p className="intake-description">Check the extracted text, cue phrase, and suggested effects.</p>
      <div className="intake-extract">
        <span className="intake-label">Page 01 · Extracted text</span>
        <p>“Mila found a tiny silver seed beside the old gate. She carried it carefully into the quiet garden and pressed it into the warm soil.”</p>
      </div>
      <dl className="intake-review">
        <div className="intake-phrase"><dt>Cue phrase</dt><dd>Mila found a tiny silver seed beside the old gate</dd></div>
        <div><dt>Sound</dt><dd>Silver seed chime</dd></div>
        <div><dt>Lighting</dt><dd>Warm amber glow</dd></div>
        <div><dt>Opening ambience</dt><dd>Quiet garden</dd></div>
      </dl>
    </>
  );
}

export function BookIntakeDemo() {
  const [stage, setStage] = useState('review');
  const currentStage = stages.find(({ id }) => id === stage);

  return (
    <main className="book-intake" aria-labelledby="book-intake-title">
      <section className="intake-hero">
        <div className="intake-intro">
          <p className="intake-label">NLB staff &amp; school team</p>
          <h2 id="book-intake-title">Add a book to the Reading Pod</h2>
          <p>Follow a sample book from page scans to a reviewed edition ready to read in the pod.</p>
          <p className="intake-demo-label">Demo · Sample data only</p>
        </div>
        <div className="intake-book">
          <img src={gardenArtwork} alt="" />
          <div><strong>Mila and the Sky Garden</strong><span>Sample book · 4 pages</span></div>
        </div>
      </section>

      <nav className="intake-stages" aria-label="Book intake stages">
        {stages.map(({ id, name, owner, status }) => (
          <button key={id} type="button" aria-pressed={id === stage} onClick={() => setStage(id)}>
            <span className="intake-label">{owner}</span>
            <strong>{name}</strong>
            <span className="intake-stage-status">{status}</span>
          </button>
        ))}
      </nav>

      <div className="intake-workspace">
        <section className="intake-card intake-stage-detail" aria-label={currentStage.name}>
          {stage === 'scans' && <ScanIntake />}
          {stage === 'processing' && <SchoolProcessing />}
          {stage === 'review' && <DraftReview />}
        </section>
        <aside className="intake-card intake-publish" aria-labelledby="intake-publish-title">
          <h3 id="intake-publish-title">Publish to the pod</h3>
          <p className="intake-description">NLB staff approve the passage, cue phrases, and effects.</p>
          <div className="intake-publish-steps">
            <div><strong>Save approved revision</strong><span>Save cue phrases, effects, and ambience to DynamoDB.</span></div>
            <div><strong>Generate book QR code</strong><span>Families scan the code to open the reading experience.</span></div>
          </div>
          <button type="button" disabled>Approve &amp; publish</button>
        </aside>
      </div>
    </main>
  );
}
