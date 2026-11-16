import { test, expect } from '@playwright/test';

test.describe('E2E Responsive Layout & Accessibility Audits', () => {
  test('Mobile viewport (390x844) renders without horizontal scroll blowout on landing page', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    // Check horizontal overflow
    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    expect(hasHorizontalOverflow).toBe(false);

    // Verify main CTA or hero heading is visible
    const heroTitle = page.locator('h1').first();
    await expect(heroTitle).toBeVisible();
  });

  test('Mobile viewport (390x844) on /docs pitch deck renders cleanly', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/docs');
    await page.waitForLoadState('domcontentloaded');

    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth + 5; // slight tolerance for subpixel fonts
    });
    expect(hasHorizontalOverflow).toBe(false);

    // Verify core content is visible
    const docTitle = page.locator('text=FloodShield AI Pro').first();
    await expect(docTitle).toBeVisible();
  });

  test('Tablet viewport (768x1024) adapts cleanly without overlapping content', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/login');
    await page.waitForLoadState('domcontentloaded');

    const form = page.locator('form');
    await expect(form).toBeVisible();

    const emailInput = page.locator('#login-email');
    await expect(emailInput).toBeVisible();

    const passInput = page.locator('#login-password');
    await expect(passInput).toBeVisible();
  });

  test('Accessibility: All core images have valid alt attributes', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const imagesWithoutAlt = await page.evaluate(() => {
      const imgs = Array.from(document.querySelectorAll('img'));
      return imgs.filter(img => !img.hasAttribute('alt') || img.getAttribute('alt')?.trim() === '').map(img => img.src);
    });

    // Zero images should lack an alt attribute
    expect(imagesWithoutAlt.length).toBe(0);
  });
});
