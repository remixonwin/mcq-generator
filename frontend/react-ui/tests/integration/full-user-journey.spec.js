import { test, expect } from '@playwright/test';
import { 
  waitForPageLoad, 
  fillForm, 
  submitForm,
  navigateToQuizCreation,
  navigateToQuizLibrary,
  navigateToMyQuizzes
} from '../utils/test-helpers';
import { mockQuizzes, mockQuestions, mockQuizAttempt, testUsers } from '../utils/mock-data';

test.describe('Full User Journey Integration', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test.beforeEach(async ({ page }) => {
    // Mock authentication
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('auth_token', 'test-token');
      localStorage.setItem('user', JSON.stringify(testUsers[0]));
    });

    // Mock comprehensive API responses
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
  });

  test('should complete full quiz creation to taking journey', async ({ page }) => {
    // Step 1: Navigate to dashboard
    await page.goto('/dashboard');
    await waitForPageLoad(page);
    await expect(page.locator('h1')).toContainText('Dashboard');
    
    // Step 2: Create new quiz
    await page.click('text=Create New Quiz');
    await waitForPageLoad(page);
    await expect(page).toHaveURL(/\/quizzes\/create/);
    
    // Step 3: Fill quiz details
    await fillForm(page, {
      'input[placeholder*="title"]': 'E2E Journey Test Quiz',
      'textarea[placeholder*="description"]': 'A quiz created during E2E testing journey'
    });
    
    await page.click('text=Science');
    await page.click('text=Medium');
    await page.click('text=Next');
    await waitForPageLoad(page);
    
    // Step 4: Skip questions for now (go to review)
    await page.click('text=Next');
    await waitForPageLoad(page);
    
    // Step 5: Review and publish
    await expect(page.locator('text=Review & Publish')).toBeVisible();
    await expect(page.locator('text=E2E Journey Test Quiz')).toBeVisible();
    
    // Mock quiz creation
    await page.route('**/api/v1/quizzes', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 999,
          title: 'E2E Journey Test Quiz',
          description: 'A quiz created during E2E testing journey',
          category: 'Science',
          difficulty: 'medium',
          is_public: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        })
      });
    });
    
    await page.click('text=Publish Quiz');
    await waitForPageLoad(page);
    
    // Step 6: Navigate to library to find new quiz
    await navigateToQuizLibrary(page);
    await waitForPageLoad(page);
    
    // Should see the new quiz in library
    await expect(page.locator('text=E2E Journey Test Quiz')).toBeVisible();
  });

  test('should complete browse to quiz taking journey', async ({ page }) => {
    // Mock specific quiz and questions
    await page.route('**/api/v1/quizzes/1', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockQuizzes[0])
      });
    });
    
    await page.route('**/api/v1/quizzes/1/questions', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockQuestions)
      });
    });
    
    await page.route('**/api/v1/quizzes/1/attempts', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 1 })
      });
    });
    
    await page.route('**/api/v1/quizzes/1/attempts/1/answers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true })
      });
    });
    
    await page.route('**/api/v1/quizzes/1/attempts/1/complete', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockQuizAttempt)
      });
    });
    
    // Step 1: Browse library
    await navigateToQuizLibrary(page);
    await waitForPageLoad(page);
    
    // Step 2: Find and select a quiz
    await expect(page.locator('text=Basic Mathematics Quiz')).toBeVisible();
    await page.click('text=Basic Mathematics Quiz');
    await waitForPageLoad(page);
    
    // Step 3: View quiz details
    await expect(page.locator('h1')).toContainText('Basic Mathematics Quiz');
    await expect(page.locator('text=Test your basic math skills')).toBeVisible();
    await expect(page.locator('text=5 questions')).toBeVisible();
    
    // Step 4: Start quiz
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Step 5: Take quiz
    await expect(page.locator('text=Question 1 of 5')).toBeVisible();
    await expect(page.locator('text=What is 15 + 27?')).toBeVisible();
    
    // Answer questions
    await page.click('text=42');
    await page.click('text=Next');
    await waitForPageLoad(page);
    
    await page.click('text=Paris');
    await page.click('text=Next');
    await waitForPageLoad(page);
    
    await page.click('text=True');
    await page.click('text=Complete Quiz');
    await waitForPageLoad(page);
    
    // Step 6: View results
    await expect(page.locator('text=Quiz Completed!')).toBeVisible();
    await expect(page.locator('text=You got 3 out of 3 questions correct')).toBeVisible();
  });

  test('should complete quiz management journey', async ({ page }) => {
    // Step 1: Go to my quizzes
    await navigateToMyQuizzes(page);
    await waitForPageLoad(page);
    
    // Step 2: View existing quizzes
    await expect(page.locator('text=Basic Mathematics Quiz')).toBeVisible();
    await expect(page.locator('text=Advanced Physics')).toBeVisible();
    
    // Step 3: Edit a quiz
    await page.click('[data-testid="quiz-card"]:first-child button:has-text("Edit")');
    await waitForPageLoad(page);
    await expect(page).toHaveURL(/\/quizzes\/\d+\/edit/);
    
    // Step 4: Navigate back to management
    await page.goto('/my-quizzes');
    await waitForPageLoad(page);
    
    // Step 5: Filter quizzes
    await page.click('text=Published');
    await waitForPageLoad(page);
    
    // Step 6: Change view mode
    await page.click('[data-testid="list-view-button"]');
    await waitForPageLoad(page);
    await expect(page.locator('[data-testid="quiz-list"]')).toBeVisible();
    
    // Step 7: Return to grid view
    await page.click('[data-testid="grid-view-button"]');
    await waitForPageLoad(page);
    await expect(page.locator('[data-testid="quiz-grid"]')).toBeVisible();
  });

  test('should handle cross-page navigation correctly', async ({ page }) => {
    // Step 1: Start at dashboard
    await page.goto('/dashboard');
    await waitForPageLoad(page);
    
    // Step 2: Navigate to library
    await page.click('text=Browse Library');
    await waitForPageLoad(page);
    await expect(page).toHaveURL(/\/library/);
    
    // Step 3: Navigate to my quizzes
    await page.goto('/my-quizzes');
    await waitForPageLoad(page);
    await expect(page).toHaveURL(/\/my-quizzes/);
    
    // Step 4: Navigate back to dashboard
    await page.goto('/dashboard');
    await waitForPageLoad(page);
    await expect(page).toHaveURL(/\/dashboard/);
    
    // Step 5: Navigate to create quiz
    await page.click('text=Create New Quiz');
    await waitForPageLoad(page);
    await expect(page).toHaveURL(/\/quizzes\/create/);
  });

  test('should handle session persistence correctly', async ({ page }) => {
    // Step 1: Login and navigate
    await page.goto('/dashboard');
    await waitForPageLoad(page);
    
    // Step 2: Navigate to different pages
    await navigateToQuizLibrary(page);
    await waitForPageLoad(page);
    
    await navigateToMyQuizzes(page);
    await waitForPageLoad(page);
    
    // Step 3: Reload page (simulate refresh)
    await page.reload();
    await waitForPageLoad(page);
    
    // Should still be authenticated
    await expect(page).toHaveURL(/\/my-quizzes/);
    await expect(page.locator('h1')).toContainText('My Quizzes');
  });

  test('should handle error recovery correctly', async ({ page }) => {
    // Step 1: Navigate to library
    await navigateToQuizLibrary(page);
    await waitForPageLoad(page);
    
    // Step 2: Simulate network error
    await page.route('**/api/v1/quizzes*', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Network error' })
      });
    });
    
    // Step 3: Refresh page
    await page.reload();
    await waitForPageLoad(page);
    
    // Should show error state
    await expect(page.locator('text=Failed to load quizzes')).toBeVisible();
    
    // Step 4: Remove error and retry
    await page.unroute('**/api/v1/quizzes*');
    await page.click('button:has-text("Retry")');
    await waitForPageLoad(page);
    
    // Should recover and show content
    await expect(page.locator('[data-testid="quiz-card"]')).toHaveCount(3);
  });

  test('should handle browser back/forward correctly', async ({ page }) => {
    // Step 1: Navigate through multiple pages
    await page.goto('/dashboard');
    await waitForPageLoad(page);
    
    await navigateToQuizLibrary(page);
    await waitForPageLoad(page);
    
    await page.goto('/quizzes/1');
    await waitForPageLoad(page);
    
    // Step 2: Use browser back
    await page.goBack();
    await waitForPageLoad(page);
    await expect(page).toHaveURL(/\/library/);
    
    // Step 3: Use browser forward
    await page.goForward();
    await waitForPageLoad(page);
    await expect(page).toHaveURL(/\/quizzes\/\d+/);
  });

  test('should handle multiple tabs correctly', async ({ page, context }) => {
    // Step 1: Open main page
    await page.goto('/dashboard');
    await waitForPageLoad(page);
    
    // Step 2: Open new tab
    const newPage = await context.newPage();
    await newPage.goto('/library');
    await waitForPageLoad(newPage);
    
    // Step 3: Both should work independently
    await expect(page.locator('h1')).toContainText('Dashboard');
    await expect(newPage.locator('h1')).toContainText('Quiz Library');
    
    // Step 4: Close new tab
    await newPage.close();
    
    // Step 5: Original page should still work
    await expect(page.locator('h1')).toContainText('Dashboard');
  });

  test('should handle data consistency across features', async ({ page }) => {
    // Create a quiz
    await page.route('**/api/v1/quizzes', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1001,
          title: 'Consistency Test Quiz',
          description: 'Testing data consistency',
          category: 'Science',
          difficulty: 'easy',
          is_public: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        })
      });
    });
    
    await navigateToQuizCreation(page);
    await fillForm(page, {
      'input[placeholder*="title"]': 'Consistency Test Quiz',
      'textarea[placeholder*="description"]': 'Testing data consistency'
    });
    await page.click('text=Science');
    await page.click('text=Easy');
    await page.click('text=Next');
    await waitForPageLoad(page);
    await page.click('text=Next');
    await waitForPageLoad(page);
    await page.click('text=Publish Quiz');
    await waitForPageLoad(page);
    
    // Check in my quizzes
    await navigateToMyQuizzes(page);
    await waitForPageLoad(page);
    await expect(page.locator('text=Consistency Test Quiz')).toBeVisible();
    
    // Check in library
    await navigateToQuizLibrary(page);
    await waitForPageLoad(page);
    await expect(page.locator('text=Consistency Test Quiz')).toBeVisible();
    
    // Data should be consistent
    const libraryCard = page.locator('[data-testid="quiz-card"]:has-text("Consistency Test Quiz")');
    await expect(libraryCard.locator('text=Science')).toBeVisible();
    await expect(libraryCard.locator('text=Easy')).toBeVisible();
  });
});
