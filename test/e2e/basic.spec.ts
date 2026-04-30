import { test, expect } from '@playwright/test';

test('has title and default watchlist', async ({ page }) => {
  await page.goto('/');

  // Expect title
  await expect(page).toHaveTitle(/FinAlly/);

  // Check for watchlist items (at least one of the defaults)
  await expect(page.getByText('RELIANCE')).toBeVisible();
  await expect(page.getByText('TCS')).toBeVisible();
});

test('can navigate to trade section', async ({ page }) => {
  await page.goto('/');
  
  // Check if portfolio total value is visible
  await expect(page.getByText('Portfolio Value')).toBeVisible();
  
  // Check if cash balance is visible
  await expect(page.getByText('Cash Balance')).toBeVisible();
});
