import { test, expect } from '@playwright/test';

const USERS = [
  { role: 'citizen', email: 'test.citizen@floodshield-demo.com', pass: 'RCkxbo4uRe82J4' },
  { role: 'health_worker', email: 'test.health_worker@floodshield-demo.com', pass: 'e2eAc$4VUqgh@x' },
  { role: 'hospital', email: 'test.hospital@floodshield-demo.com', pass: 'bWUL4VpYqLidkY' },
  { role: 'ngo', email: 'test.ngo@floodshield-demo.com', pass: 'RRSay48sQ$8B3i' },
  { role: 'government', email: 'test.government@floodshield-demo.com', pass: 'yT@XUcnrH9oFZS' },
  { role: 'admin', email: 'test.admin@floodshield-demo.com', pass: 'UGT9Tja4RiAAD3' },
];

test.describe('E2E Role-Based Access Control (RBAC)', () => {
  test('Citizen authenticates, lands on dashboard, and has restricted sidebar', async ({ page }) => {
    await page.goto('/login');
    await page.fill('#login-email', USERS[0].email);
    await page.fill('#login-password', USERS[0].pass);
    await page.click('button[type="submit"]');

    // Should redirect to dashboard
    await page.waitForURL('**/dashboard', { timeout: 15000 });
    expect(page.url()).toContain('/dashboard');

    // Verify restricted portals are NOT visible in sidebar for citizen
    const adminLink = page.locator('aside a[href="/dashboard/admin"]');
    await expect(adminLink).toHaveCount(0);

    const govLink = page.locator('aside a[href="/dashboard/government"]');
    await expect(govLink).toHaveCount(0);

    // Verify citizen navigation link is present
    const citizenReportsLink = page.locator('aside a[href="/dashboard/citizen/reports"]');
    await expect(citizenReportsLink).toBeVisible();

    // Verify navigating directly to /dashboard/admin hides all admin panels via AuthGuard
    await page.goto('/dashboard/admin');
    await page.waitForTimeout(1000);
    // Protected admin UI components must NOT render for citizen
    await expect(page.locator('text=System Administration')).toHaveCount(0);
    await expect(page.locator('text=User Management')).toHaveCount(0);
    await expect(page.locator('text=Predictions Audit')).toHaveCount(0);
  });

  test('Government coordinator authenticates and accesses Emergency Command', async ({ page }) => {
    await page.goto('/login');
    await page.fill('#login-email', USERS[4].email);
    await page.fill('#login-password', USERS[4].pass);
    await page.click('button[type="submit"]');

    await page.waitForURL('**/dashboard', { timeout: 15000 });

    // Government should see Emergency Command in sidebar
    const govLink = page.locator('aside a[href="/dashboard/government"]');
    await expect(govLink).toBeVisible();

    // Government should NOT see root Admin Panel
    const adminLink = page.locator('aside a[href="/dashboard/admin"]');
    await expect(adminLink).toHaveCount(0);
  });

  test('Super Admin authenticates and has complete unrestricted access', async ({ page }) => {
    await page.goto('/login');
    await page.fill('#login-email', USERS[5].email);
    await page.fill('#login-password', USERS[5].pass);
    await page.click('button[type="submit"]');

    await page.waitForURL('**/dashboard', { timeout: 15000 });

    // Super Admin should see Admin Panel & Automation Engine
    const adminPanelLink = page.locator('aside a[href="/dashboard/admin"]');
    await expect(adminPanelLink).toBeVisible();

    const jobsLink = page.locator('aside a[href="/dashboard/admin/jobs"]');
    await expect(jobsLink).toBeVisible();

    // Super Admin should also see Government Emergency Command
    const govLink = page.locator('aside a[href="/dashboard/government"]');
    await expect(govLink).toBeVisible();
  });
});
