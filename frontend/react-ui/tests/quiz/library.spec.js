import { test, expect } from '../utils/test-helpers';
import { waitForPageLoad } from '../utils/test-helpers';
import { mockQuizzes } from '../utils/mock-data';

test.describe('Quiz Library & Discovery', () => {
  test.beforeEach(async ({ page, mockApiResponse }) => {
    // Mock quiz library API
    mockApiResponse('/api/v1/quizzes*', 'GET', {
      quizzes: mockQuizzes,
      total: mockQuizzes.length,
      page: 1,
      per_page: 10,
      total_pages: 1,
      has_prev: false,
      has_next: false
    });
  });

  test('should display quiz library correctly', async ({ page }) => {
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Check page title
    await expect(page).toHaveTitle(/QuizMe/);
    await expect(page.locator('h1')).toContainText('Quiz Library');
    
    // Check quiz cards are displayed
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(3);
    
    // Check first quiz
    await expect(page.locator('text=Basic Mathematics Quiz')).toBeVisible();
    await expect(page.locator('text=Test your basic math skills')).toBeVisible();
    await expect(page.locator('text=5 questions')).toBeVisible();
  });

  test('should display quiz categories correctly', async ({ page }) => {
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Check category badges
    await expect(page.locator('text=Mathematics')).toBeVisible();
    await expect(page.locator('text=Geography')).toBeVisible();
    await expect(page.locator('text=Science')).toBeVisible();
    
    // Check category colors
    const mathBadge = page.locator('text=Mathematics').locator('..');
    await expect(mathBadge).toHaveClass(/bg-primary-100/);
  });

  test('should display difficulty levels correctly', async ({ page }) => {
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Check difficulty badges
    await expect(page.locator('text=Easy')).toBeVisible();
    await expect(page.locator('text=Medium')).toBeVisible();
    await expect(page.locator('text=Hard')).toBeVisible();
    
    // Check difficulty colors
    const easyBadge = page.locator('text=Easy').locator('..');
    await expect(easyBadge).toHaveClass(/bg-green-100/);
    
    const hardBadge = page.locator('text=Hard').locator('..');
    await expect(hardBadge).toHaveClass(/bg-red-100/);
  });

  test('should handle search functionality correctly', async ({ page }) => {
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Type in search
    await page.fill('input[placeholder*="Search quizzes"]', 'Mathematics');
    
    // Should trigger search (mock response would filter results)
    await page.waitForTimeout(500); // Debounce delay
    
    // Search input should have value
    await expect(page.locator('input[placeholder*="Search quizzes"]')).toHaveValue('Mathematics');
  });

  test('should handle category filtering correctly', async ({ page }) => {
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Click category filter
    await page.click('button:has-text("Category")');
    await waitForPageLoad(page);
    
    // Select Mathematics category
    await page.click('text=Mathematics');
    await waitForPageLoad(page);
    
    // Filter should be applied
    await expect(page.locator('text=Mathematics')).toBeVisible();
    // Category button should show selected state
    const categoryButton = page.locator('button:has-text("Category")');
    await expect(categoryButton).toContainText('Mathematics');
  });

  test('should handle difficulty filtering correctly', async ({ page }) => {
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Click difficulty filter
    await page.click('button:has-text("Difficulty")');
    await waitForPageLoad(page);
    
    // Select Easy difficulty
    await page.click('text=Easy');
    await waitForPageLoad(page);
    
    // Filter should be applied
    await expect(page.locator('text=Easy')).toBeVisible();
    // Difficulty button should show selected state
    const difficultyButton = page.locator('button:has-text("Difficulty")');
    await expect(difficultyButton).toContainText('Easy');
  });

  test('should handle sorting correctly', async ({ page }) => {
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Click sort dropdown
    await page.click('select');
    await waitForPageLoad(page);
    
    // Select "Most Popular"
    await page.selectOption('select', 'popularity');
    await waitForPageLoad(page);
    
    // Sort should be applied
    const sortSelect = page.locator('select');
    await expect(sortSelect).toHaveValue('popularity');
  });

  test('should handle pagination correctly', async ({ page, mockApiResponse }) => {
    // Mock paginated response
    mockApiResponse('/api/v1/quizzes*', 'GET', {
      quizzes: mockQuizzes.slice(0, 2),
      total: 5,
      page: 1,
      per_page: 2,
      total_pages: 3,
      has_prev: false,
      has_next: true
    });
    
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Should show only 2 quizzes
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(2);
    
    // Should show pagination
    await expect(page.locator('text=Previous')).toBeVisible();
    await expect(page.locator('text=Next')).toBeVisible();
    await expect(page.locator('text=Page 1 of 3')).toBeVisible();
    
    // Previous should be disabled
    await expect(page.locator('button:has-text("Previous")')).toBeDisabled();
    
    // Next should be enabled
    await expect(page.locator('button:has-text("Next")')).toBeEnabled();
  });

  test('should navigate to quiz details correctly', async ({ page }) => {
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Click on first quiz
    await page.click('[data-testid="quiz-card"]:first-child');
    await waitForPageLoad(page);
    
    // Should navigate to quiz taking page
    await expect(page).toHaveURL(/\/quizzes\/\d+/);
    await expect(page.locator('h1')).toContainText('Basic Mathematics Quiz');
  });

  test('should display empty state correctly', async ({ page, mockApiResponse }) => {
    // Mock empty response
    mockApiResponse('/api/v1/quizzes*', 'GET', {
      quizzes: [],
      total: 0,
      page: 1,
      per_page: 10,
      total_pages: 0,
      has_prev: false,
      has_next: false
    });
    
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Should show empty state
    await expect(page.locator('text=No quizzes found')).toBeVisible();
    await expect(page.locator('text=Try adjusting your filters or search terms')).toBeVisible();
  });

  test('should handle loading state correctly', async ({ page }) => {
    // Mock slow response
    await page.route('**/api/v1/quizzes*', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 2000));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ quizzes: mockQuizzes })
      });
    });
    
    await page.goto('/library');
    
    // Should show loading state
    await expect(page.locator('[data-testid="loading-spinner"]')).toBeVisible();
    
    // Should show quizzes after loading
    await waitForPageLoad(page);
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(3);
  });

  test('should handle error state correctly', async ({ page }) => {
    // Mock error response
    await page.route('**/api/v1/quizzes*', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal server error' })
      });
    });
    
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Should show error state
    await expect(page.locator('text=Failed to load quizzes')).toBeVisible();
    await expect(page.locator('text=Please try again later')).toBeVisible();
  });

  test('should display quiz stats correctly', async ({ page }) => {
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Check quiz stats on cards
    const firstCard = page.locator('[data-testid="quiz-card"]:first-child');
    await expect(firstCard.locator('text=5 questions')).toBeVisible();
    
    // Should show attempts if available (mock data would include this)
    // This depends on the actual implementation
  });

  test('should handle responsive design correctly', async ({ page }) => {
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Test mobile view
    await page.setViewportSize({ width: 375, height: 667 });
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(3);
    
    // Should stack vertically on mobile
    const cards = page.locator('[data-testid="quiz-card"]');
    const firstCardBox = await cards.first().boundingBox();
    const secondCardBox = await cards.nth(1).boundingBox();
    
    expect(secondCardBox.y).toBeGreaterThan(firstCardBox.y + firstCardBox.height);
    
    // Test desktop view
    await page.setViewportSize({ width: 1200, height: 800 });
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(3);
  });

  test('should handle keyboard navigation correctly', async ({ page }) => {
    await page.goto('/library');
    await waitForPageLoad(page);
    
    // Tab to search
    await page.keyboard.press('Tab');
    await expect(page.locator('input[placeholder*="Search quizzes"]')).toBeFocused();
    
    // Tab to first quiz card
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    
    // Should be able to activate with Enter
    await page.keyboard.press('Enter');
    await waitForPageLoad(page);
    
    await expect(page).toHaveURL(/\/quizzes\/\d+/);
  });
});
