import type { ConversationClient } from '../application/conversation';

export const fakeConversationClient: ConversationClient = {
  async ask({ question, generation }) {
    await new Promise((resolve) => setTimeout(resolve, 120));
    return {
      turnId: `fake-${generation}`,
      generation,
      text: `Foundation fake answer for: ${question}`,
      evidence: [
        {
          evidenceId: 'fake-evidence-1',
          label: 'Fake public evidence',
          sourceRef: 'fixture://portfolio-public/fossil',
        },
      ],
    };
  },
};
