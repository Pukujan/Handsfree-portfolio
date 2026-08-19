import { useState, useSyncExternalStore, type FormEvent } from 'react';
import type { HandsFreeController } from '../application/HandsFreeController';

export function App({ controller }: { controller: HandsFreeController }) {
  const snapshot = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
    controller.getSnapshot,
  );
  const [question, setQuestion] = useState('');

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const value = question.trim();
    if (!value) return;
    setQuestion('');
    void controller.submitText(value);
  };

  const toggleHandsFree = () => {
    if (snapshot.handsFreeEnabled) controller.stopHandsFree();
    else controller.startHandsFree();
  };

  const interactive = snapshot.state !== 'retrieving' && snapshot.state !== 'rendering';
  const canInterrupt = snapshot.state === 'speaking' || snapshot.state === 'retrieving' || snapshot.state === 'rendering';

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Pujan Bajracharya home">PB</a>
        <nav aria-label="Portfolio navigation">
          <a href="#work">Work</a>
          <a href="#experience">Experience</a>
          <a href="#research">Research</a>
        </nav>
      </header>

      <section className="hero" id="top">
        <p className="eyebrow">Pujan Bajracharya · AI Systems Engineer</p>
        <h1>Talk to my work.</h1>
        <p className="positioning">
          I build reliable AI systems around agent assurance, durable knowledge,
          evaluation, and high-stakes workflows.
        </p>
      </section>

      <section className="voice-stage" aria-live="polite" data-state={snapshot.state}>
        <button
          type="button"
          className="orb-button"
          onClick={canInterrupt ? () => controller.interrupt() : toggleHandsFree}
          aria-label={canInterrupt ? 'Interrupt answer' : snapshot.handsFreeEnabled ? 'Stop hands-free mode' : 'Start hands-free mode'}
        >
          <span className="aura" aria-hidden="true"><span className="core" /></span>
        </button>
        <div className="voice-copy">
          <strong>{snapshot.statusLine}</strong>
          {snapshot.interimTranscript ? <p className="interim">“{snapshot.interimTranscript}”</p> : null}
        </div>
        <div className="voice-actions">
          <button type="button" className="secondary" onClick={toggleHandsFree}>
            {snapshot.handsFreeEnabled ? 'Turn hands-free off' : 'Start hands-free'}
          </button>
          {canInterrupt ? (
            <button type="button" className="secondary" onClick={() => controller.interrupt()}>Interrupt</button>
          ) : null}
        </div>
        {!snapshot.voiceInputSupported ? (
          <p className="fallback-note">Voice recognition isn’t available in this browser. Text remains fully available.</p>
        ) : null}
      </section>

      <section className="conversation" aria-label="Portfolio conversation">
        {snapshot.lastQuestion ? <p className="question">You: {snapshot.lastQuestion}</p> : null}
        {snapshot.answerText ? <p className="answer">{snapshot.answerText}</p> : (
          <p className="empty-answer">Ask about FOSSIL, Cortex Ascend, evaluation, agent reliability, or my engineering work.</p>
        )}
        {snapshot.evidence.length ? (
          <div className="evidence" aria-label="Grounding evidence">
            {snapshot.evidence.map((item) => (
              <span key={item.evidenceId} title={item.sourceRef}>{item.label}</span>
            ))}
          </div>
        ) : null}
      </section>

      <form className="composer" onSubmit={onSubmit}>
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="What is FOSSIL and why does it matter?"
          aria-label="Ask about Pujan's work"
          disabled={!interactive}
          autoComplete="off"
        />
        <button type="submit" disabled={!interactive || !question.trim()}>Ask</button>
      </form>

      <section className="static-portfolio" id="work">
        <div className="section-heading">
          <p className="eyebrow">Selected systems</p>
          <h2>The portfolio still works without the assistant.</h2>
        </div>
        <div className="project-grid">
          <article><span>01</span><h3>FOSSIL</h3><p>Durable, provenance-backed knowledge infrastructure where projections are disposable and evidence remains canonical.</p></article>
          <article><span>02</span><h3>Cortex Ascend</h3><p>Evidence-driven assurance for bounded AI work: probabilistic workers propose; independent evidence decides admission.</p></article>
          <article><span>03</span><h3>Finance Quant</h3><p>Leakage-safe reproducible quantitative research with point-in-time data, sealed holdouts, and mechanical promotion gates.</p></article>
          <article><span>04</span><h3>Legal AI Workflow</h3><p>Confidence-gated document intelligence that separates extraction from permission to change consequential workflow state.</p></article>
        </div>
      </section>

      <section className="static-strip" id="experience">
        <p className="eyebrow">Experience</p>
        <p>AI workflow systems · applied AI engineering · document intelligence · product engineering.</p>
      </section>
      <section className="static-strip" id="research">
        <p className="eyebrow">Research</p>
        <p>Agent reliability · durable knowledge and memory · evaluation and assurance · evidence-bound workflows.</p>
      </section>
    </main>
  );
}
