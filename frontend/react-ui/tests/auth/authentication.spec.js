import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
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

  test('should display login page correctly', async ({ page }) => {
    await page.goto('/login');
    
    // Check page title and headings
    await expect(page).toHaveTitle(/QuizMe/);
    await expect(page.locator('h2')).toContainText('Welcome Back');
    await expect(page.locator('text=Sign in to your QuizMe account')).toBeVisible();
    
    // Check form elements
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await expect(page.locator('input[name="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toContainText('Sign in');
    
    // Check navigation links
    await expect(page.locator('text=Forgot your password?')).toBeVisible();
    await expect(page.locator('text=Don\'t have an account?')).toBeVisible();
    await expect(page.locator('a[href="/register"]')).toBeVisible();
  });

  test('should display registration page correctly', async ({ page }) => {
    await page.goto('/register');
    
    // Check page title and headings
    await expect(page).toHaveTitle(/QuizMe/);
    await expect(page.locator('h2')).toContainText('Create Account');
    await expect(page.locator('text=Join QuizMe and start creating amazing quizzes')).toBeVisible();
    
    // Check form elements
    await expect(page.locator('input[name="name"]')).toBeVisible();
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await expect(page.locator('input[name="password"]')).toBeVisible();
    await expect(page.locator('input[name="confirmPassword"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toContainText('Create Account');
    
    // Check password strength indicator
    await expect(page.locator('text=Password Strength')).toBeVisible();
    
    // Check navigation links
    await expect(page.locator('text=Already have an account?')).toBeVisible();
    await expect(page.locator('a[href="/login"]')).toBeVisible();
  });

  test('should show password validation errors on registration', async ({ page }) => {
    await page.goto('/register');
    
    // Try to submit empty form
    await page.click('button[type="submit"]');
    
    // Check for validation errors
    await expect(page.locator('text=Name is required')).toBeVisible();
    await expect(page.locator('text=Email is required')).toBeVisible();
    await expect(page.locator('text=Password is required')).toBeVisible();
    await expect(page.locator('text=Please confirm your password')).toBeVisible();
  });

  test('should show password mismatch error', async ({ page }) => {
    await page.goto('/register');
    
    // Fill form with mismatched passwords
    await page.fill('input[name="name"]', 'Test User');
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'password123');
    await page.fill('input[name="confirmPassword"]', 'differentpassword');
    
    await page.click('button[type="submit"]');
    
    // Check for password mismatch error
    await expect(page.locator('text=Passwords do not match')).toBeVisible();
  });

  test('should show email validation error', async ({ page }) => {
    await page.goto('/register');
    
    // Fill form with invalid email
    await page.fill('input[name="name"]', 'Test User');
    await page.fill('input[name="email"]', 'invalid-email');
    await page.fill('input[name="password"]', 'password123');
    await page.fill('input[name="confirmPassword"]', 'password123');
    
    await page.click('button[type="submit"]');
    
    // Check for email validation error
    await expect(page.locator('text=Invalid email address')).toBeVisible();
  });

  test('should toggle password visibility', async ({ page }) => {
    await page.goto('/login');
    
    const passwordInput = page.locator('input[name="password"]');
    const toggleButton = page.locator('button').filter({ hasText: '' }).first();
    
    // Initially password should be hidden
    await expect(passwordInput).toHaveAttribute('type', 'password');
    
    // Click to show password
    await toggleButton.click();
    await expect(passwordInput).toHaveAttribute('type', 'text');
    
    // Click to hide password
    await toggleButton.click();
    await expect(passwordInput).toHaveAttribute('type', 'password');
  });

  test('should navigate between login and register', async ({ page }) => {
    // Start at login page
    await page.goto('/login');
    
    // Click register link
    await page.click('a[href="/register"]');
    await expect(page).toHaveURL(/.*register/);
    await expect(page.locator('h2')).toContainText('Create Account');
    
    // Click login link
    await page.click('a[href="/login"]');
    await expect(page).toHaveURL(/.*login/);
    await expect(page.locator('h2')).toContainText('Welcome Back');
  });

  test('should protect dashboard route', async ({ page }) => {
    // Try to access dashboard without authentication
    await page.goto('/dashboard');
    
    // Should redirect to login
    await expect(page).toHaveURL(/.*login/);
  });

  test('should protect users route', async ({ page }) => {
    // Try to access users without authentication
    await page.goto('/users');
    
    // Should redirect to login
    await expect(page).toHaveURL(/.*login/);
  });

  test('should show loading state during authentication', async ({ page }) => {
    await page.goto('/login');
    
    // Fill form
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'password123');
    
    // Mock slow response to see loading state
    await page.route('**/api/v1/auth/login', route => {
      // Delay response
      setTimeout(() => {
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
      }, 1000);
    });
    
    // Submit form
    await page.click('button[type="submit"]');
    
    // Check for loading state
    await expect(page.locator('text=Signing in...')).toBeVisible();
    await expect(page.locator('.animate-spin')).toBeVisible();
  });

  test('should handle authentication errors gracefully', async ({ page }) => {
    await page.goto('/login');
    
    // Mock failed login response
    await page.route('**/api/v1/auth/login', route => {
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Invalid credentials' })
      });
    });
    
    // Fill and submit form
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');
    
    // Check for error message
    await expect(page.locator('text=Invalid credentials')).toBeVisible();
    await expect(page.locator('.bg-red-50')).toBeVisible();
  });

  test('should update UI based on authentication state', async ({ page }) => {
    // Mock successful authentication
    await page.addInitScript(() => {
      localStorage.setItem('accessToken', 'mock-token');
      localStorage.setItem('refreshToken', 'mock-refresh-token');
    });
    
    // Mock user profile endpoint
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
    
    await page.goto('/');
    
    // Check that authenticated user sees different UI
    await expect(page.locator('text=Welcome, Test User')).toBeVisible();
    await expect(page.locator('a[href="/dashboard"]')).toBeVisible();
    await expect(page.locator('text=Go to Dashboard')).toBeVisible();
    
    // Should not see login/register buttons
    await expect(page.locator('text=Sign In')).not.toBeVisible();
    await expect(page.locator('text=Sign Up')).not.toBeVisible();
  });

  test('should be mobile responsive', async ({ page }) => {
    await page.goto('/login');
    
    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    
    // Check that elements are still visible and properly sized
    await expect(page.locator('h2')).toBeVisible();
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await expect(page.locator('input[name="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
    
    // Check that some elements might be hidden on mobile
    const socialButtons = page.locator('button').filter({ hasText: 'Google' });
    await expect(socialButtons).toBeVisible();
  });
});
