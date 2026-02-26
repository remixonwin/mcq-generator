import { test, expect } from '../utils/test-helpers';

test.describe('Complete Authentication Flow', () => {
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

  test('complete registration and login flow', async ({ page }) => {
    // Step 1: Navigate to registration
    await page.goto('/');
    await page.click('a[href="/register"]');
    await expect(page).toHaveURL(/.*register/);

    // Step 2: Fill registration form
    const testUser = {
      name: 'John Doe',
      email: 'john.doe@example.com',
      password: 'SecurePassword123!'
    };

    await page.fill('input[name="name"]', testUser.name);
    await page.fill('input[name="email"]', testUser.email);
    await page.fill('input[name="password"]', testUser.password);
    await page.fill('input[name="confirmPassword"]', testUser.password);

    // Step 3: Mock successful registration
    await page.route('**/api/v1/auth/register', route => {
      route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: {
            accessToken: 'mock-access-token',
            refreshToken: 'mock-refresh-token',
            user: {
              id: 1,
              name: testUser.name,
              email: testUser.email,
              email_verified: false
            }
          }
        })
      });
    });

    // Step 4: Submit registration
    await page.click('button[type="submit"]');
    
    // Step 5: Should redirect to dashboard after successful registration
    await expect(page).toHaveURL(/.*dashboard/);
    await expect(page.locator('text=Welcome back, John Doe!')).toBeVisible();

    // Step 6: Verify user is authenticated
    await expect(page.locator('text=John Doe')).toBeVisible();
    await expect(page.locator('text=john.doe@example.com')).toBeVisible();

    // Step 7: Logout
    await page.click('button[aria-label="Logout"]');
    
    // Mock logout endpoint
    await page.route('**/api/v1/auth/logout', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          message: 'Successfully logged out'
        })
      });
    });

    // Step 8: Should redirect to home after logout
    await expect(page).toHaveURL(/.*\//);
    await expect(page.locator('text=Sign In')).toBeVisible();
    await expect(page.locator('text=Sign Up')).toBeVisible();

    // Step 9: Test login flow
    await page.click('a[href="/login"]');
    await expect(page).toHaveURL(/.*login/);

    // Step 10: Fill login form
    await page.fill('input[name="email"]', testUser.email);
    await page.fill('input[name="password"]', testUser.password);

    // Step 11: Mock successful login
    await page.route('**/api/v1/auth/login', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: {
            accessToken: 'mock-access-token-new',
            refreshToken: 'mock-refresh-token-new',
            user: {
              id: 1,
              name: testUser.name,
              email: testUser.email,
              email_verified: false
            }
          }
        })
      });
    });

    // Step 12: Submit login
    await page.click('button[type="submit"]');

    // Step 13: Should redirect to dashboard after successful login
    await expect(page).toHaveURL(/.*dashboard/);
    await expect(page.locator('text=Welcome back, John Doe!')).toBeVisible();
  });

  test('should handle session expiration gracefully', async ({ page }) => {
    // Step 1: Set up expired session
    await page.addInitScript(() => {
      localStorage.setItem('accessToken', 'expired-token');
      localStorage.setItem('refreshToken', 'expired-refresh-token');
    });

    // Step 2: Mock token refresh failure
    await page.route('**/api/v1/auth/me', route => {
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Token expired' })
      });
    });

    await page.route('**/api/v1/auth/refresh', route => {
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Refresh token expired' })
      });
    });

    // Step 3: Try to access protected route
    await page.goto('/dashboard');

    // Step 4: Should redirect to login due to expired session
    await expect(page).toHaveURL(/.*login/);
    
    // Step 5: Verify tokens are cleared
    const accessToken = await page.evaluate(() => localStorage.getItem('accessToken'));
    const refreshToken = await page.evaluate(() => localStorage.getItem('refreshToken'));
    expect(accessToken).toBeNull();
    expect(refreshToken).toBeNull();
  });

  test('should handle network errors gracefully', async ({ page }) => {
    await page.goto('/login');
    
    // Fill form
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'password123');

    // Mock network failure
    await page.route('**/api/v1/auth/login', route => {
      route.abort('failed');
    });

    // Submit form
    await page.click('button[type="submit"]');

    // Should handle network error gracefully
    await expect(page.locator('text=Login failed')).toBeVisible();
  });

  test('should maintain authentication across page refreshes', async ({ page }) => {
    // Step 1: Mock authentication
    await page.addInitScript(() => {
      localStorage.setItem('accessToken', 'mock-token');
      localStorage.setItem('refreshToken', 'mock-refresh-token');
    });

    await page.route('**/api/v1/auth/me', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: { id: 1, name: 'Test User', email: 'test@example.com' }
        })
      });
    });

    // Step 2: Go to dashboard
    await page.goto('/dashboard');
    await expect(page.locator('text=Welcome back, Test User!')).toBeVisible();

    // Step 3: Refresh page
    await page.reload();

    // Step 4: Should still be authenticated
    await expect(page.locator('text=Welcome back, Test User!')).toBeVisible();
    await expect(page).toHaveURL(/.*dashboard/);
  });

  test('should handle concurrent tab authentication', async ({ page, context }) => {
    // Step 1: Authenticate in first tab
    await page.addInitScript(() => {
      localStorage.setItem('accessToken', 'mock-token');
      localStorage.setItem('refreshToken', 'mock-refresh-token');
    });

    await page.route('**/api/v1/auth/me', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: { id: 1, name: 'Test User', email: 'test@example.com' }
        })
      });
    });

    await page.goto('/dashboard');
    await expect(page.locator('text=Welcome back, Test User!')).toBeVisible();

    // Step 2: Open new tab
    const newPage = await context.newPage();
    
    // Step 3: New tab should also be authenticated (shared localStorage)
    await newPage.goto('/dashboard');
    await expect(newPage.locator('text=Welcome back, Test User!')).toBeVisible();

    // Step 4: Logout from one tab
    await page.route('**/api/v1/auth/logout', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          message: 'Successfully logged out'
        })
      });
    });

    await page.click('button[aria-label="Logout"]');

    // Step 5: Both tabs should be logged out
    await expect(page).toHaveURL(/.*\//);
    await expect(newPage).toHaveURL(/.*\//);
  });

  test('should validate password strength in real-time', async ({ page }) => {
    await page.goto('/register');
    
    const passwordInput = page.locator('input[name="password"]');
    const strengthIndicator = page.locator('text=Password Strength');
    const strengthBar = page.locator('.bg-gray-200').first();

    // Test weak password
    await passwordInput.fill('weak');
    await expect(strengthIndicator).toBeVisible();
    await expect(page.locator('text=Very Weak')).toBeVisible();
    
    // Test strong password
    await passwordInput.fill('StrongPassword123!');
    await expect(page.locator('text=Very Strong')).toBeVisible();
    
    // Check all validation indicators
    await expect(page.locator('text=At least 8 characters')).toBeVisible();
    await expect(page.locator('text=One uppercase letter')).toBeVisible();
    await expect(page.locator('text=One number')).toBeVisible();
    await expect(page.locator('text=One special character')).toBeVisible();
  });

  test('should handle form submission with enter key', async ({ page }) => {
    await page.goto('/login');
    
    // Fill form and press enter
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'password123');
    await page.press('input[name="password"]', 'Enter');

    // Mock successful login
    await page.route('**/api/v1/auth/login', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          data: {
            accessToken: 'mock-token',
            refreshToken: 'mock-refresh-token',
            user: { id: 1, name: 'Test User', email: 'test@example.com' }
          }
        })
      });
    });

    // Should submit and redirect
    await expect(page).toHaveURL(/.*dashboard/);
  });
});
