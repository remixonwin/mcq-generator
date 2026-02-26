import { test, expect } from '../utils/test-helpers';
import { 
  waitForPageLoad, 
  navigateToQuizCreation,
  navigateToQuizLibrary,
  navigateToMyQuizzes
} from '../utils/test-helpers';
import { mockQuizzes } from '../utils/mock-data';

test.describe('Mobile Responsiveness', () => {
  const mobileViewport = { width: 375, height: 667 };
  const tabletViewport = { width: 768, height: 1024 };

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

    // Mock API responses
    await page.route('**/api/v1/quizzes*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          quizzes: mockQuizzes,
          total: mockQuizzes.length,
          page: 1,
          per_page: 10,
          total_pages: 1,
          has_prev: false,
          has_next: false
        })
      });
    });
  });

  test('should display quiz library correctly on mobile', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await navigateToQuizLibrary(page);
    
    // Check mobile layout
    await expect(page.locator('h1')).toContainText('Quiz Library');
    
    // Check mobile search
    const searchInput = page.locator('input[placeholder*="Search quizzes"]');
    await expect(searchInput).toBeVisible();
    await expect(searchInput).toHaveCSS('width', /\d+px/);
    
    // Check quiz cards stack vertically
    const cards = page.locator('[data-testid="quiz-card"]');
    await expect(cards).toHaveCount(3);
    
    const firstCardBox = await cards.first().boundingBox();
    const secondCardBox = await cards.nth(1).boundingBox();
    expect(secondCardBox.y).toBeGreaterThan(firstCardBox.y + firstCardBox.height);
  });

  test('should display quiz creation wizard correctly on mobile', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await navigateToQuizCreation(page);
    
    // Check mobile header
    await expect(page.locator('h1')).toContainText('Create Quiz');
    
    // Progress steps should be compact on mobile
    const progressSteps = page.locator('[data-testid="progress-step"]');
    await expect(progressSteps).toHaveCount(3);
    
    // Form should be full width
    const formContainer = page.locator('[data-testid="quiz-form"]');
    await expect(formContainer).toBeVisible();
  });

  test('should display my quizzes correctly on mobile', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await navigateToMyQuizzes(page);
    
    // Check mobile dashboard
    await expect(page.locator('h1')).toContainText('My Quizzes');
    
    // Stats should stack vertically on mobile
    const statsCards = page.locator('[data-testid="stat-card"]');
    await expect(statsCards).toHaveCount(4);
    
    // Check vertical stacking
    const firstStatBox = await statsCards.first().boundingBox();
    const secondStatBox = await statsCards.nth(1).boundingBox();
    expect(secondStatBox.y).toBeGreaterThan(firstStatBox.y + firstStatBox.height);
  });

  test('should handle mobile navigation correctly', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await navigateToQuizLibrary(page);
    
    // Check mobile menu button (if exists)
    const mobileMenuButton = page.locator('[data-testid="mobile-menu-button"]');
    if (await mobileMenuButton.isVisible()) {
      await mobileMenuButton.click();
      
      // Should show mobile menu
      await expect(page.locator('[data-testid="mobile-menu"]')).toBeVisible();
    }
  });

  test('should handle mobile touch interactions correctly', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await navigateToQuizLibrary(page);
    
    // Test touch on quiz card
    const firstCard = page.locator('[data-testid="quiz-card"]:first-child');
    await firstCard.tap();
    await waitForPageLoad(page);
    
    // Should navigate to quiz
    await expect(page).toHaveURL(/\/quizzes\/\d+/);
  });

  test('should handle mobile scrolling correctly', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await navigateToQuizLibrary(page);
    
    // Check page is scrollable on mobile
    const pageHeight = await page.evaluate(() => document.body.scrollHeight);
    const viewportHeight = mobileViewport.height;
    
    expect(pageHeight).toBeGreaterThan(viewportHeight);
    
    // Test scrolling
    await page.evaluate(() => window.scrollTo(0, 500));
    await page.waitForTimeout(500);
    
    // Should scroll smoothly
    const scrollY = await page.evaluate(() => window.scrollY);
    expect(scrollY).toBeGreaterThan(0);
  });

  test('should display quiz taking correctly on mobile', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    
    // Mock quiz data
    await page.route('**/api/v1/quizzes/1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockQuizzes[0])
      });
    });
    
    await page.goto('/quizzes/1');
    await waitForPageLoad(page);
    
    // Check mobile quiz layout
    await expect(page.locator('h1')).toContainText(mockQuizzes[0].title);
    
    // Start button should be prominent on mobile
    const startButton = page.locator('button:has-text("Start Quiz")');
    await expect(startButton).toBeVisible();
    await expect(startButton).toHaveCSS('width', /\d+px/);
  });

  test('should handle mobile quiz questions correctly', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    
    // Mock quiz questions
    await page.route('**/api/v1/quizzes/1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockQuizzes[0])
      });
    });
    
    await page.goto('/quizzes/1');
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Check mobile question layout
    await expect(page.locator('text=Question 1 of')).toBeVisible();
    
    // Options should be stacked on mobile
    const options = page.locator('input[type="radio"]');
    await expect(options).toHaveCount(4);
    
    // Each option should be full width
    const firstOption = options.first();
    const optionBox = await firstOption.boundingBox();
    expect(optionBox.width).toBeGreaterThan(300); // Should be wide on mobile
  });

  test('should handle tablet view correctly', async ({ page }) => {
    await page.setViewportSize(tabletViewport);
    await navigateToQuizLibrary(page);
    
    // Check tablet layout
    await expect(page.locator('h1')).toContainText('Quiz Library');
    
    // Should show 2 columns on tablet
    const cards = page.locator('[data-testid="quiz-card"]');
    const firstCardBox = await cards.first().boundingBox();
    const secondCardBox = await cards.nth(1).boundingBox();
    
    // Cards should be side by side on tablet
    expect(secondCardBox.y).toBeCloseTo(firstCardBox.y, 10);
    expect(secondCardBox.x).toBeGreaterThan(firstCardBox.x);
  });

  test('should handle mobile form inputs correctly', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await navigateToQuizCreation(page);
    
    // Test mobile input focus
    const titleInput = page.locator('input[placeholder*="title"]');
    await titleInput.tap();
    await waitForPageLoad(page);
    
    // Should show mobile keyboard (simulated)
    await expect(titleInput).toBeFocused();
    
    // Test typing on mobile
    await titleInput.fill('Mobile Test Quiz');
    await expect(titleInput).toHaveValue('Mobile Test Quiz');
  });

  test('should handle mobile dropdowns correctly', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await navigateToQuizLibrary(page);
    
    // Test mobile dropdown
    const categoryDropdown = page.locator('button:has-text("Category")');
    await categoryDropdown.tap();
    await waitForPageLoad(page);
    
    // Should show mobile-friendly dropdown
    await expect(page.locator('[data-testid="category-options"]')).toBeVisible();
    
    // Select option
    await page.click('text=Science');
    await waitForPageLoad(page);
    
    // Should update selection
    await expect(categoryDropdown).toContainText('Science');
  });

  test('should handle mobile pagination correctly', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await navigateToQuizLibrary(page);
    
    // Pagination should be mobile-friendly
    const pagination = page.locator('[data-testid="pagination"]');
    if (await pagination.isVisible()) {
      // Buttons should be appropriately sized for mobile
      const prevButton = pagination.locator('button:has-text("Previous")');
      const nextButton = pagination.locator('button:has-text("Next")');
      
      if (await prevButton.isVisible()) {
        const prevBox = await prevButton.boundingBox();
        expect(prevBox.height).toBeGreaterThan(40); // Touch-friendly height
      }
      
      if (await nextButton.isVisible()) {
        const nextBox = await nextButton.boundingBox();
        expect(nextBox.height).toBeGreaterThan(40); // Touch-friendly height
      }
    }
  });

  test('should handle mobile orientation change correctly', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await navigateToQuizLibrary(page);
    
    // Start in portrait
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(3);
    
    // Change to landscape
    await page.setViewportSize({ width: 667, height: 375 });
    await waitForPageLoad(page);
    
    // Should adapt to landscape
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(3);
    
    // Layout should adjust
    const cards = page.locator('[data-testid="quiz-card"]');
    const firstCardBox = await cards.first().boundingBox();
    expect(firstCardBox.width).toBeGreaterThan(200); // Should be wider in landscape
  });

  test('should handle mobile accessibility correctly', async ({ page }) => {
    await page.setViewportSize(mobileViewport);
    await navigateToQuizLibrary(page);
    
    // Test keyboard navigation on mobile
    await page.keyboard.press('Tab');
    await expect(page.locator('input[placeholder*="Search quizzes"]')).toBeFocused();
    
    // Test screen reader compatibility
    const quizCards = page.locator('[data-testid="quiz-card"]');
    await expect(quizCards.first()).toHaveAttribute('role', 'button');
    await expect(quizCards.first()).toHaveAttribute('aria-label');
  });
});
