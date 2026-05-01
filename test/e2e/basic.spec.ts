import { test, expect } from '@playwright/test';

async function guestLogin(page: import('@playwright/test').Page) {
  // Wait for auth gate to appear
  await expect(page.getByText('FinAlly')).toBeVisible();
  // Click the guest login button
  await page.getByRole('button', { name: /Try as Guest/i }).click();
  // Wait for the trading app to load (auth gate disappears)
  await expect(page.getByText('AI Trading Workstation')).toBeVisible({ timeout: 10000 });
}

test('has title and default watchlist', async ({ page }) => {
  await page.goto('/');

  // Expect title
  await expect(page).toHaveTitle(/FinAlly/);

  // Log in as guest before asserting on app state
  await guestLogin(page);

  // Check for watchlist items (at least one of the defaults)
  await expect(page.getByText('RELIANCE')).toBeVisible();
  await expect(page.getByText('TCS')).toBeVisible();
});

test('can navigate to trade section', async ({ page }) => {
  await page.goto('/');

  // Log in as guest before asserting on app state
  await guestLogin(page);

  // Header labels match what the Header component actually renders
  await expect(page.getByText('Total Value')).toBeVisible();
  await expect(page.getByText('Cash')).toBeVisible();
});
