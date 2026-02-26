import { test, expect } from '@playwright/test';

test.describe('Basic Application Tests', () => {
  test('should load the application', async ({ page }) => {
    await page.goto('/');
    
    // Check that the page loads
    await expect(page).toHaveTitle(/QuizMe/);
  });

  test('should navigate to login page', async ({ page }) => {
    await page.goto('/login');
    
    // Check login page elements
    await expect(page.locator('h2')).toContainText('Welcome Back');
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await expect(page.locator('input[name="password"]')).toBeVisible();
  });

  test('should navigate to register page', async ({ page }) => {
    await page.goto('/register');
    
    // Check register page elements
    await expect(page.locator('h2')).toContainText('Create Account');
    await expect(page.locator('input[name="name"]')).toBeVisible();
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await expect(page.locator('input[name="password"]')).toBeVisible();
  });
});
