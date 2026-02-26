import { test, expect } from '@playwright/test';

test.describe('Backend Integration Tests', () => {
  test.beforeEach(async ({ page, context }) => {
    // Clear storage before each test
    await context.clearCookies();
    await page.goto('/');
    await page.evaluate(() => {
      try {
        localStorage.clear();
      } catch (e) {
        // Ignore localStorage errors
      }
    });
  });

  test('should register user with real backend', async ({ page }) => {
    // Navigate to registration
    await page.goto('/register');
    await expect(page).toHaveURL(/.*register/);

    // Fill registration form
    const testUser = {
      name: 'Integration Test User',
      email: 'integration@example.com',
      password: 'IntegrationPassword123!'
    };

    await page.fill('input[name="name"]', testUser.name);
    await page.fill('input[name="email"]', testUser.email);
    await page.fill('input[name="password"]', testUser.password);
    await page.fill('input[name="confirmPassword"]', testUser.password);

    // Submit form
    await page.click('button[type="submit"]');

    // Wait for registration to complete (should redirect to dashboard)
    await expect(page).toHaveURL(/.*dashboard/);
    
    // Verify user is logged in
    await expect(page.locator('text=Welcome back, Integration Test User!')).toBeVisible();
  });

  test('should login user with real backend', async ({ page }) => {
    // First register a user
    await page.goto('/register');
    
    const testUser = {
      name: 'Login Test User',
      email: 'login@example.com',
      password: 'LoginPassword123!'
    };

    await page.fill('input[name="name"]', testUser.name);
    await page.fill('input[name="email"]', testUser.email);
    await page.fill('input[name="password"]', testUser.password);
    await page.fill('input[name="confirmPassword"]', testUser.password);

    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/.*dashboard/);

    // Logout
    await page.click('button[aria-label="Logout"]');
    await expect(page).toHaveURL(/.*\//);

    // Now test login
    await page.goto('/login');
    await expect(page).toHaveURL(/.*login/);

    await page.fill('input[name="email"]', testUser.email);
    await page.fill('input[name="password"]', testUser.password);

    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/.*dashboard/);
    await expect(page.locator('text=Welcome back, Login Test User!')).toBeVisible();
  });

  test('should protect dashboard route', async ({ page }) => {
    // Try to access dashboard without authentication
    await page.goto('/dashboard');
    
    // Should redirect to login
    await expect(page).toHaveURL(/.*login/);
  });
});
