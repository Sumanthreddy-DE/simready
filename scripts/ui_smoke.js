const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const screenshots = [];
  try {
    await page.goto('http://127.0.0.1:8501', { waitUntil: 'networkidle', timeout: 30000 });
    await page.setViewportSize({ width: 1440, height: 1400 });
    await page.screenshot({ path: '/tmp/simready-streamlit-home.png', fullPage: true });
    screenshots.push('/tmp/simready-streamlit-home.png');

    const input = page.locator('input[type="file"]');
    await input.setInputFiles(path.resolve('tests/data/smoke_box.step'));
    await page.waitForTimeout(3000);
    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    await page.screenshot({ path: '/tmp/simready-streamlit-smoke-box.png', fullPage: true });
    screenshots.push('/tmp/simready-streamlit-smoke-box.png');

    const bodyText = await page.locator('body').innerText();
    const checks = {
      hasSimReady: bodyText.includes('SimReady'),
      hasScoreBreakdown: bodyText.includes('Score Breakdown'),
      hasGraphTopology: bodyText.includes('Graph Topology'),
      hasFindings: bodyText.includes('Findings'),
      hasMLDetails: bodyText.includes('ML Details'),
      hasStatusLabel: bodyText.includes('ReviewRecommended') || bodyText.includes('SimulationReady') || bodyText.includes('NeedsAttention') || bodyText.includes('NotReady'),
      hasSmokeFilename: bodyText.includes('smoke_box.step'),
    };
    console.log(JSON.stringify({ ok: true, checks, screenshots }, null, 2));
  } catch (error) {
    console.error(JSON.stringify({ ok: false, error: String(error), screenshots }, null, 2));
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
