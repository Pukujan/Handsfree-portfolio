import { useRef, useState, type FormEvent } from 'react';
import type { ConversationAnswer, ConversationClient, ConversationState } from '../application/conversation';

export function App({ conversation }: { conversation: ConversationClient }) {
  const [state, setState] = useState<ConversationState>('idle');
  const [answer, setAnswer] = useState<ConversationAnswer | null>(null);
  const [question, setQuestion] = useState('');
  const generation = useRef(0);

  const ask = async (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return;
    generation.current += 1;
    const mine = generation.current;
    setState('retrieving');
    const result = await conversation.ask({ question: trimmed, generation: mine });
    if (result.generation !== generation.current) return;
    setAnswer(result);
    setState('idle');
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void ask(question);
    setQuestion('');
  };

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">Pujan Bajracharya · AI Systems Engineer</p>
        <h1>Talk to my work.</h1>
        <p className="positioning">I build reliable AI systems around agent assurance, durable knowledge, evaluation, and high-stakes workflows.</p>
      </section>

      <section className="voice" aria-live="polite" data-state={state}>
        <div className="aura" aria-hidden="true"><div className="core" /></div>
        <strong>{state === 'retrieving' ? 'Checking public evidence…' : 'Ready'}</strong>
      </section>

      <section className="conversation">
        {answer ? (
          <>
            <p>{answer.text}</p>
            <div className="evidence">
              {answer.evidence.map((item) => <span key={item.evidenceId}>{item.label}</span>)}
            </div>
          </>
        ) : <p>Ask a question. This G0 build intentionally uses a deterministic fake adapter.</p>}
      </section>

      <form className="composer" onSubmit={onSubmit}>
        <input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What is FOSSIL?" aria-label="Ask about Pujan's work" />
        <button type="submit">Ask</button>
      </form>
    </main>
  );
}
