import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const URL = 'file:///C:/Users/35796/Documents/coding%E9%A1%B9%E7%9B%AE/%E5%9B%BE%E6%96%87%E6%8E%92%E7%89%88/social-card-demo/index.html';

const posters = [
  { id: 'xhs-01', name: 'xhs-01-cover' },
  { id: 'xhs-02', name: 'xhs-02-capabilities' },
  { id: 'xhs-03', name: 'xhs-03-summary' },
];

mkdirSync('output', { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto(URL, { waitUntil: 'networkidle' });
await page.waitForTimeout(1000);

for (const poster of posters) {
  const el = await page.locator(`#${poster.id}`);
  await el.screenshot({ path: `output/${poster.name}.png` });
  console.log(`✓ ${poster.name}.png`);
}

await browser.close();
console.log('Done — 3 posters rendered.');
