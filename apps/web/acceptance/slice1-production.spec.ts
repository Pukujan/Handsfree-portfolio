import { dirname } from 'node:path';
import { mkdirSync, writeFileSync } from 'node:fs';
import { expect, test, type BrowserContext, type Request, type Response } from '@playwright/test';

const FIRST_QUESTION = 'What is FOSSIL and why does it matter?';
const SECOND_QUESTION = 'Why not just use Neo4j?';
const FIRST_ANSWER = "FOSSIL's durable knowledge authority is its evidence.";
const SECOND_ANSWER = 'Graphiti and Neo4j are replaceable projections of already-durable FOSSIL knowledge.';
const FOSSIL_SOURCE_PREFIX = 'Pukujan/fossil-core@b5fd57725c910b149910371964adb35d9280016e:ARCHITECTURE.md';

type Slice1Window = Window & typeof globalThis & {
  __slice1RecognitionStarts?: number;
  __slice1Spoken?: string[];
  __slice1FinishSpeech?: () => void;
};

async function installDeterministicBrowserSpeech(context: BrowserContext): Promise<void> {
  await context.addInitScript(({ questions }) => {
    const state = window as Slice1Window;
    state.__slice1RecognitionStarts = 0;
    state.__slice1Spoken = [];

    class FakeRecognition {
      continuous = false;
      interimResults = false;
      lang = '';
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: unknown) => void) | null = null;
      onend: (() => void) | null = null;

      start() {
        const index = state.__slice1RecognitionStarts || 0;
        state.__slice1RecognitionStarts = index + 1;
        const question = questions[index];
        if (!question) return;
        setTimeout(() => {
          this.onresult?.({
            resultIndex: 0,
            results: {
              0: { 0: { transcript: question }, isFinal: true },
              length: 1,
            },
          });
        }, 20);
      }

      stop() {}
      abort() {}
    }

    class FakeUtterance {
      text: string;
      rate = 1;
      pitch = 1;
      onstart: (() => void) | null = null;
      onend: (() => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      constructor(text: string) { this.text = text; }
    }

    let pending: FakeUtterance | null = null;
    state.__slice1FinishSpeech = () => {
      const utterance = pending;
      pending = null;
      utterance?.onend?.();
    };

    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: FakeRecognition });
    Object.defineProperty(window, 'webkitSpeechRecognition', { configurable: true, value: undefined });
    Object.defineProperty(window, 'SpeechSynthesisUtterance', { configurable: true, value: FakeUtterance });
    Object.defineProperty(window, 'speechSynthesis', {
      configurable: true,
      value: {
        speak(utterance: FakeUtterance) {
          pending = utterance;
          state.__slice1Spoken?.push(utterance.text);
          utterance.onstart?.();
        },
        cancel() { pending = null; },
      },
    });
  }, { questions: [FIRST_QUESTION, SECOND_QUESTION] });
}

function isTurnRequest(request: Request): boolean {
  return request.method() === 'POST' && /\/v1\/conversations\/[^/]+\/turns$/.test(new URL(request.url()).pathname);
}

function isTurnResponse(response: Response): boolean {
  return isTurnRequest(response.request());
}

test('production Slice-1 completes the exact two-turn spoken FOSSIL journey and relistens', async ({ browser }) => {
  const workflowSha = process.env.EXPECTED_SHA || '';
  const receiptPath = process.env.SLICE1_RECEIPT_PATH || '';
  expect(workflowSha).toMatch(/^[0-9a-f]{40}$/);
  expect(receiptPath).not.toBe('');

  const context = await browser.newContext();
  await installDeterministicBrowserSpeech(context);
  const page = await context.newPage();
  const turnRequests: Request[] = [];
  const turnResponses: Response[] = [];
  page.on('request', (request) => { if (isTurnRequest(request)) turnRequests.push(request); });
  page.on('response', (response) => { if (isTurnResponse(response)) turnResponses.push(response); });

  await page.goto('/');
  await expect(page.getByText('Pujan Bajracharya · AI Systems Engineer', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Talk to my work.' })).toBeVisible();

  await page.getByRole('button', { name: 'Start hands-free mode' }).click();

  await expect(page.getByText(`You: ${FIRST_QUESTION}`, { exact: true })).toBeVisible();
  await expect(page.locator('.answer')).toHaveText(FIRST_ANSWER);
  const firstEvidence = page.getByLabel('Grounding evidence').locator('span').first();
  await expect(firstEvidence).toBeVisible();
  const firstEvidenceLabel = (await firstEvidence.innerText()).trim();
  const firstEvidenceSourceRef = await firstEvidence.getAttribute('title');
  expect(firstEvidenceSourceRef).toBe(FOSSIL_SOURCE_PREFIX);

  await expect.poll(async () => page.evaluate(() => (window as Slice1Window).__slice1Spoken || []))
    .toEqual([FIRST_ANSWER]);
  const startsBeforeFirstFinish = await page.evaluate(() => (window as Slice1Window).__slice1RecognitionStarts || 0);
  expect(startsBeforeFirstFinish).toBe(1);

  await page.evaluate(() => (window as Slice1Window).__slice1FinishSpeech?.());

  await expect(page.getByText(`You: ${SECOND_QUESTION}`, { exact: true })).toBeVisible();
  await expect(page.locator('.answer')).toHaveText(SECOND_ANSWER);
  const secondEvidence = page.getByLabel('Grounding evidence').locator('span').first();
  await expect(secondEvidence).toBeVisible();
  const secondEvidenceLabel = (await secondEvidence.innerText()).trim();
  const secondEvidenceSourceRef = await secondEvidence.getAttribute('title');
  expect(secondEvidenceSourceRef).toBe(FOSSIL_SOURCE_PREFIX);

  await expect.poll(async () => page.evaluate(() => (window as Slice1Window).__slice1Spoken || []))
    .toEqual([FIRST_ANSWER, SECOND_ANSWER]);
  const startsBeforeSecondFinish = await page.evaluate(() => (window as Slice1Window).__slice1RecognitionStarts || 0);
  expect(startsBeforeSecondFinish).toBe(2);

  await page.evaluate(() => (window as Slice1Window).__slice1FinishSpeech?.());
  await expect(page.locator('.voice-stage')).toHaveAttribute('data-state', 'listening');
  await expect.poll(async () => page.evaluate(() => (window as Slice1Window).__slice1RecognitionStarts || 0))
    .toBe(3);

  expect(turnRequests).toHaveLength(2);
  expect(turnResponses).toHaveLength(2);
  const requestQuestions = turnRequests.map((request) => (request.postDataJSON() as { question: string }).question);
  expect(requestQuestions).toEqual([FIRST_QUESTION, SECOND_QUESTION]);
  const conversationUrls = turnRequests.map((request) => request.url());
  expect(new Set(conversationUrls).size).toBe(1);
  expect(turnResponses.map((response) => response.status())).toEqual([200, 200]);
  const contentTypes = await Promise.all(turnResponses.map((response) => response.headerValue('content-type')));
  for (const contentType of contentTypes) expect(contentType).toContain('text/event-stream');

  const spokenAnswers = await page.evaluate(() => (window as Slice1Window).__slice1Spoken || []);
  const recognitionStarts = await page.evaluate(() => (window as Slice1Window).__slice1RecognitionStarts || 0);
  const receipt = {
    status: 'SLICE1_MACHINE_PASS',
    authority: 'production_edge_real_api_real_fossil_deterministic_browser_speech',
    workflowSha,
    browser: 'chromium',
    productionSameOriginEdge: true,
    actualSseResponses: 2,
    questions: requestQuestions,
    sameConversationIdAcrossTurns: true,
    firstAnswer: FIRST_ANSWER,
    secondAnswer: SECOND_ANSWER,
    firstEvidence: { label: firstEvidenceLabel, sourceRef: firstEvidenceSourceRef },
    secondEvidence: { label: secondEvidenceLabel, sourceRef: secondEvidenceSourceRef },
    spokenAnswers,
    speechOnlyAfterGroundedUiState: true,
    relistenAfterFirstAnswer: startsBeforeSecondFinish === 2,
    relistenAfterSecondAnswer: recognitionStarts === 3,
    noNetworkMocking: true,
  };
  mkdirSync(dirname(receiptPath), { recursive: true });
  writeFileSync(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`, 'utf-8');
  console.log(JSON.stringify(receipt));
  await context.close();
});
