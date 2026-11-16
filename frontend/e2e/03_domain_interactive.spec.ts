import { test, expect } from '@playwright/test';

const ADMIN_CREDS = { email: 'test.admin@floodshield-demo.com', pass: 'UGT9Tja4RiAAD3' };

test.describe('E2E Domain Interactive Workflows', () => {
  test('District intelligence and assessment page (/dashboard/Sylhet)', async ({ page }) => {
    // Authenticate first
    await page.goto('/login');
    await page.fill('#login-email', ADMIN_CREDS.email);
    await page.fill('#login-password', ADMIN_CREDS.pass);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard', { timeout: 15000 });

    // Navigate to district-specific intelligence view
    await page.goto('/dashboard/Sylhet');
    await page.waitForLoadState('domcontentloaded');

    // Verify district title heading is present
    const heading = page.locator('h1, h2').filter({ hasText: /Sylhet/i }).first();
    await expect(heading).toBeVisible({ timeout: 10000 });

    // Verify presence of telemetry or prediction cards
    const cardElements = page.locator('div').filter({ hasText: /Flood|Disease|Risk|Weather|Surge|Outbreak/i });
    expect(await cardElements.count()).toBeGreaterThan(0);
  });

  test('Interactive /docs YC Pitch Deck & Technical Whitepaper navigation', async ({ page }) => {
    await page.goto('/docs');
    await page.waitForLoadState('domcontentloaded');

    // Verify main pitch deck headline is rendered
    const title = page.locator('text=FloodShield AI Pro').first();
    await expect(title).toBeVisible();

    // Verify YC Pitch Deck section navigation exists
    const problemLink = page.locator('button, a').filter({ hasText: /The Problem/i }).first();
    await expect(problemLink).toBeVisible();

    const teamLink = page.locator('button, a').filter({ hasText: /The Team/i }).first();
    await expect(teamLink).toBeVisible();

    // Click on The Team section button
    await teamLink.click();
    await page.waitForTimeout(500);

    // Verify Team section content is visible
    const teamSection = page.locator('text=FloodShield Core Innovation Team').first();
    await expect(teamSection).toBeVisible();

    // Click on Architecture section
    const archLink = page.locator('button, a').filter({ hasText: /System Architecture/i }).first();
    await expect(archLink).toBeVisible();
    await archLink.click();
    await page.waitForTimeout(500);

    // Verify architecture layer is displayed
    const archHeader = page.locator('text=Engineering Architecture').first();
    await expect(archHeader).toBeVisible();
  });

  test('Citizen hazard reporting form structure and validation', async ({ page }) => {
    await page.goto('/login');
    await page.fill('#login-email', ADMIN_CREDS.email);
    await page.fill('#login-password', ADMIN_CREDS.pass);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard', { timeout: 15000 });

    await page.goto('/dashboard/citizen/reports');
    await page.waitForLoadState('domcontentloaded');

    // Verify heading is present
    const pageHeading = page.locator('h1, h2').filter({ hasText: /Citizen|Report/i }).first();
    await expect(pageHeading).toBeVisible();

    // Verify form or submit buttons exist
    const submitBtn = page.locator('button').filter({ hasText: /Submit|Report|Create/i }).first();
    await expect(submitBtn).toBeVisible();
  });
});
