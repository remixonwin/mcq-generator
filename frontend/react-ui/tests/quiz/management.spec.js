import { test, expect } from '../utils/test-helpers';
import { 
  waitForPageLoad, 
  navigateToMyQuizzes 
} from '../utils/test-helpers';
import { mockQuizzes } from '../utils/mock-data';

test.describe('Quiz Management Dashboard', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test.beforeEach(async ({ page }) => {
    // Mock authentication
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('auth_token', 'test-token');
      localStorage.setItem('user', JSON.stringify({
        id: 1,
        name: 'Test User',
        email: 'test@example.com'
      }));
    });

    // Mock user's quizzes
    await page.route('**/api/v1/quizzes?created_by=1*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          quizzes: mockQuizzes.filter(q => q.created_by === 1),
          total: 2,
          page: 1,
          per_page: 10,
          total_pages: 1,
          has_prev: false,
          has_next: false
        })
      });
    });

    // Mock quiz deletion
    await page.route('**/api/v1/quizzes/1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true })
      });
    });
  });

  test('should display my quizzes dashboard correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Check page title
    await expect(page).toHaveTitle(/QuizMe/);
    await expect(page.locator('h1')).toContainText('My Quizzes');
    await expect(page.locator('text=Manage and track your quiz creations')).toBeVisible();
    
    // Check create quiz button
    await expect(page.locator('text=Create Quiz')).toBeVisible();
  });

  test('should display quiz statistics correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Check stats cards
    await expect(page.locator('text=Total Quizzes')).toBeVisible();
    await expect(page.locator('text=Total Attempts')).toBeVisible();
    await expect(page.locator('text=Avg. Score')).toBeVisible();
    await expect(page.locator('text=Avg. Time')).toBeVisible();
    
    // Check stats values
    await expect(page.locator('text=2')).toBeVisible(); // Total quizzes
  });

  test('should display user quizzes correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Should show user's quizzes
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(2);
    
    // Check quiz details
    await expect(page.locator('text=Basic Mathematics Quiz')).toBeVisible();
    await expect(page.locator('text=Advanced Physics')).toBeVisible();
    
    // Check published/draft status
    await expect(page.locator('text=Published')).toBeVisible();
    await expect(page.locator('text=Draft')).toBeVisible();
  });

  test('should handle view mode toggle correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Check default grid view
    await expect(page.locator('[data-testid="quiz-grid"]')).toBeVisible();
    
    // Switch to list view
    await page.click('[data-testid="list-view-button"]');
    await waitForPageLoad(page);
    
    // Should show list view
    await expect(page.locator('[data-testid="quiz-list"]')).toBeVisible();
    
    // Switch back to grid view
    await page.click('[data-testid="grid-view-button"]');
    await waitForPageLoad(page);
    
    // Should show grid view again
    await expect(page.locator('[data-testid="quiz-grid"]')).toBeVisible();
  });

  test('should handle filter tabs correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Check filter tabs
    await expect(page.locator('text=All Quizzes')).toBeVisible();
    await expect(page.locator('text=Published')).toBeVisible();
    await expect(page.locator('text=Drafts')).toBeVisible();
    
    // Click Published filter
    await page.click('text=Published');
    await waitForPageLoad(page);
    
    // Should filter results
    await expect(page.locator('text=Published')).toHaveClass(/bg-primary-600/);
    
    // Click Drafts filter
    await page.click('text=Drafts');
    await waitForPageLoad(page);
    
    // Should filter results
    await expect(page.locator('text=Drafts')).toHaveClass(/bg-primary-600/);
  });

  test('should handle sorting correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Check sort dropdown
    await expect(page.locator('select')).toBeVisible();
    await expect(page.locator('text=Recently Created')).toBeVisible();
    
    // Change sort
    await page.selectOption('select', 'title');
    await waitForPageLoad(page);
    
    // Should apply sort
    const sortSelect = page.locator('select');
    await expect(sortSelect).toHaveValue('title');
  });

  test('should navigate to quiz edit correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Click edit button on first quiz
    await page.click('[data-testid="quiz-card"]:first-child button:has-text("Edit")');
    await waitForPageLoad(page);
    
    // Should navigate to edit page
    await expect(page).toHaveURL(/\/quizzes\/\d+\/edit/);
  });

  test('should navigate to quiz view correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Click view button on first quiz
    await page.click('[data-testid="quiz-card"]:first-child button:has-text("View")');
    await waitForPageLoad(page);
    
    // Should navigate to quiz page
    await expect(page).toHaveURL(/\/quizzes\/\d+/);
  });

  test('should handle quiz deletion correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Click delete button on first quiz
    await page.click('[data-testid="quiz-card"]:first-child button:has-text("Delete")');
    
    // Should show confirmation dialog
    await expect(page.locator('text=Are you sure you want to delete this quiz?')).toBeVisible();
    await expect(page.locator('text=This action cannot be undone')).toBeVisible();
    
    // Confirm deletion
    await page.click('button:has-text("Delete")');
    await waitForPageLoad(page);
    
    // Quiz should be removed from list
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(1);
  });

  test('should cancel quiz deletion correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Click delete button
    await page.click('[data-testid="quiz-card"]:first-child button:has-text("Delete")');
    
    // Cancel deletion
    await page.click('button:has-text("Cancel")');
    
    // Dialog should close
    await expect(page.locator('text=Are you sure you want to delete this quiz?')).not.toBeVisible();
    
    // Quiz should still be in list
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(2);
  });

  test('should display empty state correctly', async ({ page }) => {
    // Mock empty response
    await page.route('**/api/v1/quizzes?created_by=1*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          quizzes: [],
          total: 0,
          page: 1,
          per_page: 10,
          total_pages: 0,
          has_prev: false,
          has_next: false
        })
      });
    });
    
    await navigateToMyQuizzes(page);
    
    // Should show empty state
    await expect(page.locator('text=No Quizzes Yet')).toBeVisible();
    await expect(page.locator('text=Start creating your first quiz')).toBeVisible();
    await expect(page.locator('button:has-text("Create Your First Quiz")')).toBeVisible();
  });

  test('should handle create quiz navigation correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Click create quiz button
    await page.click('button:has-text("Create Quiz")');
    await waitForPageLoad(page);
    
    // Should navigate to creation page
    await expect(page).toHaveURL(/\/quizzes\/create/);
  });

  test('should display quiz metadata correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Check quiz cards show metadata
    const firstCard = page.locator('[data-testid="quiz-card"]:first-child');
    
    await expect(firstCard.locator('text=5 questions')).toBeVisible();
    await expect(firstCard.locator('text=Mathematics')).toBeVisible();
    await expect(firstCard.locator('text=Easy')).toBeVisible();
    await expect(firstCard.locator('text=Published')).toBeVisible();
  });

  test('should handle list view layout correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Switch to list view
    await page.click('[data-testid="list-view-button"]');
    await waitForPageLoad(page);
    
    // Check list layout
    await expect(page.locator('[data-testid="quiz-list-item"]')).toHaveCount(2);
    
    // Check list item content
    const firstItem = page.locator('[data-testid="quiz-list-item"]:first-child');
    await expect(firstItem.locator('text=Basic Mathematics Quiz')).toBeVisible();
    await expect(firstItem.locator('text=Test your basic math skills')).toBeVisible();
    await expect(firstItem.locator('text=5 questions')).toBeVisible();
    await expect(firstItem.locator('text=Created')).toBeVisible();
  });

  test('should handle responsive design correctly', async ({ page }) => {
    await navigateToMyQuizzes(page);
    
    // Test mobile view
    await page.setViewportSize({ width: 375, height: 667 });
    
    // Should adapt to mobile
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(2);
    
    // Stats should stack vertically
    await expect(page.locator('[data-testid="stats-grid"]')).toBeVisible();
    
    // Test tablet view
    await page.setViewportSize({ width: 768, height: 1024 });
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(2);
    
    // Test desktop view
    await page.setViewportSize({ width: 1200, height: 800 });
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(2);
  });

  test('should handle loading state correctly', async ({ page }) => {
    // Mock slow response
    await page.route('**/api/v1/quizzes?created_by=1*', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 2000));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ quizzes: mockQuizzes.filter(q => q.created_by === 1) })
      });
    });
    
    await navigateToMyQuizzes(page);
    
    // Should show loading state
    await expect(page.locator('[data-testid="loading-spinner"]')).toBeVisible();
    
    // Should show quizzes after loading
    await waitForPageLoad(page);
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(2);
  });

  test('should handle error state correctly', async ({ page }) => {
    // Mock error response
    await page.route('**/api/v1/quizzes?created_by=1*', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal server error' })
      });
    });
    
    await navigateToMyQuizzes(page);
    await waitForPageLoad(page);
    
    // Should show error state
    await expect(page.locator('text=Error Loading Quizzes')).toBeVisible();
    await expect(page.locator('text=Please try again later')).toBeVisible();
  });
});
