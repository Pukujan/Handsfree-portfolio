import AxeBuilder from '@axe-core/playwright';
import { expect, test, type BrowserContext, type Page } from '@playwright/test';

const QUESTION = 'What is FOSSIL?';
const ANSWER = "FOSSIL's durable knowledge authority is its evidence.";
const EVIDENCE_ID = 'fixture:fossil:evidence';
const SOURCE_REF = 'Pukujan/fossil-core@b5fd57725c910b149910371964adb35d9280016e:ARCHITECTURE.md';
const EVIDENCE_LABEL = 'FOSSIL architecture';

function event(type: string, payload: Record<string, unknown>, generation = 1): string {
  return `event: ${type}\ndata: ${JSON.stringify({ type, turnId: 'browser-turn-1', generation, payload })}\n\n`;
}

function groundedSse(): string {
  return [
    event('turn.accepted', { activeSubject: 'FOSSIL' }),
    event('retrieval.started', {}),
    event('evidence.found', { evidenceIds: [EVIDENCE_ID] }),
    event('answer.planned', {
      evidence: [{ evidenceId: EVIDENCE_ID, sourceRef: SOURCE_REF, label: EVIDENCE_LABEL }],
    }),
    event('answer.delta', { text: ANSWER, claimIds: ['clm_portfolio_fossil_durable_truth_0001'] }),
    event('answer.grounded', {
      claimIds: ['clm_portfolio_fossil_durable_truth_0001'],
      evidenceIds: [EVIDENCE_ID],
    }),
    event('turn.complete', {
      claimIds: ['clm_portfolio_fossil_durable_truth_0001'],
      evidenceIds: [EVIDENCE_ID],
    }),
  ].join('');
}

async function mockGroundedApi(page: Page): Promise<void> {
  await page.route('**/v1/conversations/*/turns', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    await route.fulfill({
      status: 200,
      headers: {
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-cache',
      },
      body: groundedSse(),
    });
  });
}

async function installUnsupportedSpeech(context: BrowserContext): Promise<void> {
  await context.addInitScript(() => {
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: undefined });
    Object.defineProperty(window, 'webkitSpeechRecognition', { configurable: true, value: undefined });
  });
}

async function installSuccessfulSpeech(context: BrowserContext): Promise<void> {
  await context.addInitScript(({ question }) => {
    type Recognition = {
      continuous: boolean;
      interimResults: boolean;
      lang: string;
      onresult: ((event: unknown) => void) | null;
      onerror: ((event: unknown) => void) | null;
      onend: (() => void) | null;
      start(): void;
      stop(): void;
      abort(): void;
    };

    class FakeRecognition implements Recognition {
      continuous = false;
      interimResults = false;
      lang = '';
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: unknown) => void) | null = null;
      onend: (() => void) | null = null;

      start() {
        const state = window as Window & { __g8SpeechQuestionSent?: boolean };
        if (state.__g8SpeechQuestionSent) return;
        state.__g8SpeechQuestionSent = true;
        setTimeout(() => {
          this.onresult?.({
            resultIndex: 0,
            results: {
              0: { 0: { transcript: question }, isFinal: true },
              length: 1,
            },
          });
        }, 0);
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

    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: FakeRecognition });
    Object.defineProperty(window, 'SpeechSynthesisUtterance', { configurable: true, value: FakeUtterance });
    Object.defineProperty(window, 'speechSynthesis', {
      configurable: true,
      value: {
        speak(utterance: FakeUtterance) {
          utterance.onstart?.();
          setTimeout(() => utterance.onend?.(), 0);
        },
        cancel() {},
      },
    });
  }, { question: QUESTION });
}

async function installDeniedSpeech(context: BrowserContext): Promise<void> {
  await context.addInitScript(() => {
    class DeniedRecognition {
      continuous = false;
      interimResults = false;
      lang = '';
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: { error: string; message: string }) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        setTimeout(() => {
          this.onerror?.({ error: 'not-allowed', message: 'permission denied' });
          this.onend?.();
        }, 0);
      }
      stop() {}
      abort() {}
    }
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: DeniedRecognition });
  });
}

test('static/text fallback is keyboard-usable and has no serious axe violations', async ({ browser }) => {
  const context = await browser.newContext();
  await installUnsupportedSpeech(context);
  const page = await context.newPage();
  await mockGroundedApi(page);
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Talk to my work.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'The portfolio still works without the assistant.' })).toBeVisible();
  await expect(page.getByText('Voice recognition isn’t available in this browser. Text remains fully available.')).toBeVisible();

  const audit = await new AxeBuilder({ page }).analyze();
  const blocking = audit.violations.filter((violation) => violation.impact === 'critical' || violation.impact === 'serious');
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);

  const focusNames: string[] = [];
  for (let index = 0; index < 10; index += 1) {
    await page.keyboard.press('Tab');
    focusNames.push(await page.evaluate(() => {
      const element = document.activeElement as HTMLElement | null;
      if (!element) return '';
      return element.getAttribute('aria-label')
        || element.getAttribute('placeholder')
        || element.textContent?.trim()
        || element.tagName;
    }));
  }
  expect(focusNames).toContain('Start hands-free mode');
  expect(focusNames).toContain("Ask about Pujan's work");

  const input = page.getByRole('textbox', { name: "Ask about Pujan's work" });
  await input.fill(QUESTION);
  await input.press('Enter');
  await expect(page.getByText(ANSWER, { exact: true })).toBeVisible();
  const evidence = page.getByLabel('Grounding evidence').getByText(EVIDENCE_LABEL, { exact: true });
  await expect(evidence).toBeVisible();
  await expect(evidence).toHaveAttribute('title', SOURCE_REF);
  await context.close();
});

test('360px mobile viewport has no horizontal overflow and keeps primary controls usable', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto('/');

  const layout = await page.evaluate(() => ({
    viewportWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(layout.scrollWidth).toBeLessThanOrEqual(layout.viewportWidth);

  const orb = await page.getByRole('button', { name: 'Start hands-free mode' }).boundingBox();
  const input = await page.getByRole('textbox', { name: "Ask about Pujan's work" }).boundingBox();
  expect(orb).not.toBeNull();
  expect(input).not.toBeNull();
  expect(orb!.width).toBeGreaterThanOrEqual(44);
  expect(orb!.height).toBeGreaterThanOrEqual(44);
  expect(input!.height).toBeGreaterThanOrEqual(44);
  expect(input!.x).toBeGreaterThanOrEqual(0);
  expect(input!.x + input!.width).toBeLessThanOrEqual(360);

  await page.getByRole('textbox', { name: "Ask about Pujan's work" }).fill('FOSSIL?');
  const ask = await page.getByRole('button', { name: 'Ask' }).boundingBox();
  expect(ask).not.toBeNull();
  expect(ask!.height).toBeGreaterThanOrEqual(44);
  expect(ask!.x + ask!.width).toBeLessThanOrEqual(360);
});

test('reduced-motion preference disables the animated aura', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  const animationName = await page.locator('.aura').evaluate((element) => getComputedStyle(element).animationName);
  expect(animationName).toBe('none');
});

test('microphone denial degrades to text/static behavior without disabling the composer', async ({ browser }) => {
  const context = await browser.newContext();
  await installDeniedSpeech(context);
  const page = await context.newPage();
  await page.goto('/');

  await page.getByRole('button', { name: 'Start hands-free mode' }).click();
  await expect(page.getByText('Microphone access is unavailable. You can keep using the text input.')).toBeVisible();
  await expect(page.getByRole('textbox', { name: "Ask about Pujan's work" })).toBeEnabled();
  await expect(page.getByRole('heading', { name: 'The portfolio still works without the assistant.' })).toBeVisible();
  await context.close();
});

test('hands-free and text controls render identical grounded answer and evidence', async ({ browser }) => {
  const textContext = await browser.newContext();
  const textPage = await textContext.newPage();
  await mockGroundedApi(textPage);
  await textPage.goto('/');
  const textInput = textPage.getByRole('textbox', { name: "Ask about Pujan's work" });
  await textInput.fill(QUESTION);
  await textInput.press('Enter');
  await expect(textPage.getByText(ANSWER, { exact: true })).toBeVisible();
  const textAnswer = await textPage.locator('.answer').innerText();
  const textEvidence = await textPage.getByLabel('Grounding evidence').innerText();

  const voiceContext = await browser.newContext();
  await installSuccessfulSpeech(voiceContext);
  const voicePage = await voiceContext.newPage();
  await mockGroundedApi(voicePage);
  await voicePage.goto('/');
  await voicePage.getByRole('button', { name: 'Start hands-free mode' }).click();
  await expect(voicePage.getByText(ANSWER, { exact: true })).toBeVisible();
  const voiceAnswer = await voicePage.locator('.answer').innerText();
  const voiceEvidence = await voicePage.getByLabel('Grounding evidence').innerText();

  expect(voiceAnswer).toBe(textAnswer);
  expect(voiceEvidence).toBe(textEvidence);
  await textContext.close();
  await voiceContext.close();
});
