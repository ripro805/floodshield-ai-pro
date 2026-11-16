import { test, expect } from '@playwright/test';

const PAGES = [
  { path: '/', titleSnippet: 'FloodShield' },
  { path: '/login', titleSnippet: 'FloodShield' },
  { path: '/signup', titleSnippet: 'FloodShield' },
  { path: '/forgot-password', titleSnippet: 'FloodShield' },
  { path: '/dashboard', titleSnippet: 'FloodShield' },
  { path: '/dashboard/Sylhet', titleSnippet: 'FloodShield' },
  { path: '/dashboard/alerts', titleSnippet: 'FloodShield' },
  { path: '/dashboard/reports', titleSnippet: 'FloodShield' },
  { path: '/dashboard/citizen/reports', titleSnippet: 'FloodShield' },
  { path: '/dashboard/resources', titleSnippet: 'FloodShield' },
  { path: '/docs', titleSnippet: 'FloodShield' },
];

test.describe('E2E Smoke Suite: Core Application Pages', () => {
  for (const p of PAGES) {
    test(`Page ${p.path} loads cleanly without console runtime crashes`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on('console', msg => {
        if (msg.type() === 'error') {
          consoleErrors.push(msg.text());
        }
      });

      page.on('pageerror', err => {
        consoleErrors.push(err.message);
      });

      const response = await page.goto(p.path, { waitUntil: 'domcontentloaded', timeout: 30000 });
      expect(response?.status()).toBeLessThan(400);

      // Verify page is not completely blank
      const bodyText = await page.textContent('body');
      expect(bodyText?.trim().length).toBeGreaterThan(10);

      // Verify title or logo
      await expect(page).toHaveTitle(new RegExp(p.titleSnippet, 'i'));

      // Filter out harmless hydration or 3D canvas resource warnings
      const fatalErrors = consoleErrors.filter(
        err => !err.includes('WebGL') && !err.includes('Hydration') && !err.includes('favicon')
      );
      expect(fatalErrors.length).toBe(0);
    });
  }
});
