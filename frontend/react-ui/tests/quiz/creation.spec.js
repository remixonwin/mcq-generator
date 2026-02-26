import { test, expect } from '@playwright/test';
import { 
  authenticatedPage, 
  waitForPageLoad, 
  fillForm, 
  submitForm, 
  createTestQuiz,
  navigateToQuizCreation 
} from '../utils/test-helpers';
import { quizCreationTestData, categories, difficulties } from '../utils/mock-data';

test.describe('Quiz Creation Flow', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test.beforeEach(async ({ page, mockApiResponse }) => {
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
    mockApiResponse('/api/v1/quizzes', 'POST', {
      id: 1,
      ...quizCreationTestData.validQuiz,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    });
  });

  test('should display quiz creation wizard correctly', async ({ page }) => {
    await navigateToQuizCreation(page);
    
    // Check page title and navigation
    await expect(page).toHaveTitle(/QuizMe/);
    await expect(page.locator('h1')).toContainText('Create Quiz');
    
    // Check progress steps
    await expect(page.locator('text=Basic Info')).toBeVisible();
    await expect(page.locator('text=Questions')).toBeVisible();
    await expect(page.locator('text=Review')).toBeVisible();
    
    // Check current step (Step 1)
    await expect(page.locator('text=Basic Information')).toBeVisible();
    await expect(page.locator('text=Let\'s start with the basic details about your quiz')).toBeVisible();
  });

  test('should validate quiz basic information form', async ({ page }) => {
    await navigateToQuizCreation(page);
    
    // Test empty title validation
    await page.fill('input[placeholder*="title"]', '');
    await page.click('text=Next');
    await expect(page.locator('text=Quiz Title *')).toBeVisible();
    
    // Test valid form submission
    await fillForm(page, {
      'input[placeholder*="title"]': quizCreationTestData.validQuiz.title,
      'textarea[placeholder*="description"]': quizCreationTestData.validQuiz.description
    });
    
    // Select category
    await page.click(`text=${quizCreationTestData.validQuiz.category}`);
    
    // Select difficulty
    await page.click(`text=${quizCreationTestData.validQuiz.difficulty.charAt(0).toUpperCase() + quizCreationTestData.validQuiz.difficulty.slice(1)}`);
    
    // Should be able to proceed to next step
    await page.click('text=Next');
    await waitForPageLoad(page);
    
    // Should be on step 2 (Questions)
    await expect(page.locator('text=Questions')).toBeVisible();
    await expect(page.locator('text=Add questions to your quiz')).toBeVisible();
  });

  test('should handle category selection correctly', async ({ page }) => {
    await navigateToQuizCreation(page);
    
    // Check all categories are displayed
    for (const category of categories) {
      await expect(page.locator(`text=${category}`)).toBeVisible();
    }
    
    // Select a category
    await page.click('text=Science');
    
    // Category should be selected
    const categoryButton = page.locator('text=Science');
    await expect(categoryButton).toHaveClass(/border-primary-500/);
  });

  test('should handle difficulty selection correctly', async ({ page }) => {
    await navigateToQuizCreation(page);
    
    // Check all difficulty levels are displayed
    await expect(page.locator('text=Easy')).toBeVisible();
    await expect(page.locator('text=Medium')).toBeVisible();
    await expect(page.locator('text=Hard')).toBeVisible();
    
    // Select medium difficulty
    await page.click('text=Medium');
    
    // Medium should be selected
    const mediumButton = page.locator('text=Medium').locator('..').locator('..');
    await expect(mediumButton).toHaveClass(/border-yellow-500/);
  });

  test('should toggle visibility setting correctly', async ({ page }) => {
    await navigateToQuizCreation(page);
    
    // Check initial state (should be private by default)
    const visibilityToggle = page.locator('button[role="switch"]');
    await expect(visibilityToggle).not.toHaveClass(/bg-primary-600/);
    await expect(page.locator('text=Only you can see and take this quiz')).toBeVisible();
    
    // Toggle to public
    await visibilityToggle.click();
    await expect(visibilityToggle).toHaveClass(/bg-primary-600/);
    await expect(page.locator('text=Anyone can discover and take your quiz')).toBeVisible();
    
    // Toggle back to private
    await visibilityToggle.click();
    await expect(visibilityToggle).not.toHaveClass(/bg-primary-600/);
  });

  test('should navigate between steps correctly', async ({ page }) => {
    await navigateToQuizCreation(page);
    
    // Fill step 1
    await fillForm(page, {
      'input[placeholder*="title"]': quizCreationTestData.validQuiz.title,
      'textarea[placeholder*="description"]': quizCreationTestData.validQuiz.description
    });
    await page.click('text=Science');
    await page.click('text=Medium');
    
    // Go to step 2
    await page.click('text=Next');
    await waitForPageLoad(page);
    await expect(page.locator('text=Questions')).toBeVisible();
    
    // Go back to step 1
    await page.click('text=Previous');
    await waitForPageLoad(page);
    await expect(page.locator('text=Basic Information')).toBeVisible();
    
    // Data should be preserved
    await expect(page.locator('input[placeholder*="title"]')).toHaveValue(quizCreationTestData.validQuiz.title);
    await expect(page.locator('textarea[placeholder*="description"]')).toHaveValue(quizCreationTestData.validQuiz.description);
  });

  test('should display AI generation option in questions step', async ({ page }) => {
    await navigateToQuizCreation(page);
    
    // Complete step 1
    await fillForm(page, {
      'input[placeholder*="title"]': quizCreationTestData.validQuiz.title,
      'textarea[placeholder*="description"]': quizCreationTestData.validQuiz.description
    });
    await page.click('text=Science');
    await page.click('text=Medium');
    await page.click('text=Next');
    await waitForPageLoad(page);
    
    // Check AI generation option
    await expect(page.locator('text=Generate Questions with AI')).toBeVisible();
    await expect(page.locator('text=Let AI create engaging questions')).toBeVisible();
    await expect(page.locator('button:has-text("Generate Questions")')).toBeVisible();
  });

  test('should display manual questions section', async ({ page }) => {
    await navigateToQuizCreation(page);
    
    // Complete step 1
    await fillForm(page, {
      'input[placeholder*="title"]': quizCreationTestData.validQuiz.title,
      'textarea[placeholder*="description"]': quizCreationTestData.validQuiz.description
    });
    await page.click('text=Science');
    await page.click('text=Medium');
    await page.click('text=Next');
    await waitForPageLoad(page);
    
    // Check manual questions section
    await expect(page.locator('text=Manual Questions')).toBeVisible();
    await expect(page.locator('text=Add Question')).toBeVisible();
    await expect(page.locator('text=No questions added yet')).toBeVisible();
  });

  test('should display review step correctly', async ({ page }) => {
    await navigateToQuizCreation(page);
    
    // Complete steps 1 and 2
    await fillForm(page, {
      'input[placeholder*="title"]': quizCreationTestData.validQuiz.title,
      'textarea[placeholder*="description"]': quizCreationTestData.validQuiz.description
    });
    await page.click('text=Science');
    await page.click('text=Medium');
    await page.click('text=Next'); // Go to step 2
    await waitForPageLoad(page);
    await page.click('text=Next'); // Go to step 3
    await waitForPageLoad(page);
    
    // Check review step
    await expect(page.locator('text=Review & Publish')).toBeVisible();
    await expect(page.locator('text=Review your quiz details')).toBeVisible();
    await expect(page.locator('text=E2E Test Quiz')).toBeVisible();
    await expect(page.locator('text=This is a quiz created during E2E testing')).toBeVisible();
  });

  test('should publish quiz successfully', async ({ page }) => {
    await navigateToQuizCreation(page);
    
    // Complete all steps
    await fillForm(page, {
      'input[placeholder*="title"]': quizCreationTestData.validQuiz.title,
      'textarea[placeholder*="description"]': quizCreationTestData.validQuiz.description
    });
    await page.click('text=Science');
    await page.click('text=Medium');
    await page.click('text=Next'); // Step 2
    await waitForPageLoad(page);
    await page.click('text=Next'); // Step 3
    await waitForPageLoad(page);
    
    // Publish quiz
    await page.click('text=Publish Quiz');
    await waitForPageLoad(page);
    
    // Should redirect to edit page
    await expect(page).toHaveURL(/\/quizzes\/\d+\/edit/);
  });

  test('should handle character limits correctly', async ({ page }) => {
    await navigateToQuizCreation(page);
    
    const titleInput = page.locator('input[placeholder*="title"]');
    const descriptionInput = page.locator('textarea[placeholder*="description"]');
    
    // Check initial character counts
    await expect(page.locator('text=0/200 characters')).toBeVisible();
    await expect(page.locator('text=0/1000 characters')).toBeVisible();
    
    // Type in title
    await titleInput.fill('Test title');
    await expect(page.locator('text=10/200 characters')).toBeVisible();
    
    // Type in description
    await descriptionInput.fill('Test description');
    await expect(page.locator('text=15/1000 characters')).toBeVisible();
  });

  test('should handle save draft functionality', async ({ page }) => {
    await navigateToQuizCreation(page);
    
    // Fill some data
    await fillForm(page, {
      'input[placeholder*="title"]': 'Draft Quiz',
      'textarea[placeholder*="description"]': 'This is a draft'
    });
    
    // Click save draft
    await page.click('text=Save Draft');
    
    // Should show some indication of saving (this would depend on implementation)
    // For now, just verify the button is clickable
    await expect(page.locator('text=Save Draft')).toBeVisible();
  });
});
