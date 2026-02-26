import { test, expect } from '@playwright/test';
import { waitForPageLoad } from '../utils/test-helpers';
import { mockQuizzes, mockQuestions, mockQuizAttempt } from '../utils/mock-data';

test.describe('Quiz Taking Experience', () => {
  test.beforeEach(async ({ page, mockApiResponse }) => {
    // Mock quiz data
    mockApiResponse('/api/v1/quizzes/1', 'GET', mockQuizzes[0]);
    mockApiResponse('/api/v1/quizzes/1/attempts', 'POST', { id: 1 });
    mockApiResponse('/api/v1/quizzes/1/attempts/1/answers', 'POST', { success: true });
    mockApiResponse('/api/v1/quizzes/1/attempts/1/complete', 'POST', mockQuizAttempt);
    
    // Mock questions
    mockApiResponse('/api/v1/quizzes/1/questions', 'GET', mockQuestions);
  });

  test('should display quiz start page correctly', async ({ page }) => {
    await page.goto('/quizzes/1');
    await waitForPageLoad(page);
    
    // Check quiz information
    await expect(page.locator('h1')).toContainText(mockQuizzes[0].title);
    await expect(page.locator('text=Basic Mathematics Quiz')).toBeVisible();
    await expect(page.locator('text=Test your basic math skills')).toBeVisible();
    
    // Check quiz metadata
    await expect(page.locator('text=5 questions')).toBeVisible();
    await expect(page.locator('text=Easy difficulty')).toBeVisible();
    await expect(page.locator('text=Science')).toBeVisible();
  });

  test('should start quiz attempt correctly', async ({ page }) => {
    await page.goto('/quizzes/1');
    await waitForPageLoad(page);
    
    // Start the quiz
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Should be on first question
    await expect(page.locator('text=Question 1 of 5')).toBeVisible();
    await expect(page.locator('text=What is 15 + 27?')).toBeVisible();
  });

  test('should display multiple choice questions correctly', async ({ page }) => {
    await page.goto('/quizzes/1');
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Check question and options
    await expect(page.locator('text=What is 15 + 27?')).toBeVisible();
    
    // Check all options are displayed
    await expect(page.locator('text=40')).toBeVisible();
    await expect(page.locator('text=41')).toBeVisible();
    await expect(page.locator('text=42')).toBeVisible();
    await expect(page.locator('text=43')).toBeVisible();
    
    // Check radio buttons
    const radioButtons = page.locator('input[type="radio"]');
    await expect(radioButtons).toHaveCount(4);
  });

  test('should handle answer selection correctly', async ({ page }) => {
    await page.goto('/quizzes/1');
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Select an answer
    await page.click('text=42');
    
    // Radio button should be selected
    const selectedRadio = page.locator('input[value="42"]');
    await expect(selectedRadio).toBeChecked();
    
    // Option should be highlighted
    const selectedOption = page.locator('text=42').locator('..').locator('..');
    await expect(selectedOption).toHaveClass(/border-primary-500/);
  });

  test('should navigate between questions correctly', async ({ page }) => {
    await page.goto('/quizzes/1');
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Select answer for first question
    await page.click('text=42');
    
    // Go to next question
    await page.click('text=Next');
    await waitForPageLoad(page);
    
    // Should be on question 2
    await expect(page.locator('text=Question 2 of 5')).toBeVisible();
    await expect(page.locator('text=What is the capital of France?')).toBeVisible();
    
    // Go back to previous question
    await page.click('text=Previous');
    await waitForPageLoad(page);
    
    // Should be back on question 1
    await expect(page.locator('text=Question 1 of 5')).toBeVisible();
    await expect(page.locator('text=What is 15 + 27?')).toBeVisible();
    
    // Answer should be preserved
    await expect(page.locator('input[value="42"]')).toBeChecked();
  });

  test('should display progress correctly', async ({ page }) => {
    await page.goto('/quizzes/1');
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Check initial progress
    await expect(page.locator('text=Question 1 of 5')).toBeVisible();
    await expect(page.locator('text=1/5 answered')).toBeVisible();
    
    // Progress bar should be at 20%
    const progressBar = page.locator('.bg-primary-600').first();
    await expect(progressBar).toHaveCSS('width', '20%');
    
    // Answer question and go to next
    await page.click('text=42');
    await page.click('text=Next');
    await waitForPageLoad(page);
    
    // Progress should update
    await expect(page.locator('text=Question 2 of 5')).toBeVisible();
    await expect(page.locator('text=1/5 answered')).toBeVisible();
  });

  test('should handle timer correctly', async ({ page }) => {
    await page.goto('/quizzes/1');
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Timer should be visible
    await expect(page.locator('[data-testid="timer"]')).toBeVisible();
    
    // Should start at 0:00
    await expect(page.locator('text=0:00')).toBeVisible();
    
    // Wait a moment and check timer increments
    await page.waitForTimeout(2000);
    const timerText = await page.locator('[data-testid="timer"]').textContent();
    expect(timerText).toMatch(/\d+:\d+/);
    expect(timerText).not.toBe('0:00');
  });

  test('should prevent navigation without answering', async ({ page }) => {
    await page.goto('/quizzes/1');
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Next button should be disabled without answer
    const nextButton = page.locator('text=Next');
    await expect(nextButton).toBeDisabled();
    
    // Select answer
    await page.click('text=42');
    
    // Next button should be enabled
    await expect(nextButton).toBeEnabled();
  });

  test('should handle true/false questions correctly', async ({ page }) => {
    // Mock a true/false question
    await page.route('**/api/v1/quizzes/1/questions', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 3,
          quiz_id: 1,
          question_text: 'Is the Earth round?',
          question_type: 'true_false',
          options: JSON.stringify(['True', 'False']),
          correct_answer: 0,
          points: 5,
          time_limit: 10
        }])
      });
    });
    
    await page.goto('/quizzes/1');
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Check true/false question
    await expect(page.locator('text=Is the Earth round?')).toBeVisible();
    await expect(page.locator('text=True')).toBeVisible();
    await expect(page.locator('text=False')).toBeVisible();
    
    // Should only have 2 options
    const radioButtons = page.locator('input[type="radio"]');
    await expect(radioButtons).toHaveCount(2);
  });

  test('should complete quiz successfully', async ({ page }) => {
    await page.goto('/quizzes/1');
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Answer all questions
    await page.click('text=42');
    await page.click('text=Next');
    await waitForPageLoad(page);
    
    await page.click('text=Paris');
    await page.click('text=Next');
    await waitForPageLoad(page);
    
    await page.click('text=True');
    await page.click('text=Complete Quiz');
    await waitForPageLoad(page);
    
    // Should show results
    await expect(page.locator('text=Quiz Completed!')).toBeVisible();
    await expect(page.locator('text=80%')).toBeVisible();
    await expect(page.locator('text=You got 3 out of 3 questions correct')).toBeVisible();
  });

  test('should display quiz results correctly', async ({ page }) => {
    await page.goto('/quizzes/1');
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Complete quiz quickly
    await page.click('text=42');
    await page.click('text=Next');
    await waitForPageLoad(page);
    
    await page.click('text=Paris');
    await page.click('text=Next');
    await waitForPageLoad(page);
    
    await page.click('text=True');
    await page.click('text=Complete Quiz');
    await waitForPageLoad(page);
    
    // Check results details
    await expect(page.locator('text=Total Quizzes')).toBeVisible();
    await expect(page.locator('text=Correct Answers')).toBeVisible();
    await expect(page.locator('text=Incorrect Answers')).toBeVisible();
    await expect(page.locator('text=Time Spent')).toBeVisible();
    
    // Check question review
    await expect(page.locator('text=Question Review')).toBeVisible();
    await expect(page.locator('text=What is 15 + 27?')).toBeVisible();
    await expect(page.locator('text=Your answer: 42')).toBeVisible();
    await expect(page.locator('text=Correct answer: 42')).toBeVisible();
  });

  test('should handle quiz exit gracefully', async ({ page }) => {
    await page.goto('/quizzes/1');
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Click back to library
    await page.click('text=←').first(); // Back button
    await waitForPageLoad(page);
    
    // Should return to library
    await expect(page).toHaveURL(/\/library/);
  });

  test('should handle time limit questions', async ({ page }) => {
    // Mock question with time limit
    await page.route('**/api/v1/quizzes/1/questions', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 1,
          quiz_id: 1,
          question_text: 'Quick math question',
          question_type: 'multiple_choice',
          options: JSON.stringify(['1', '2', '3', '4']),
          correct_answer: 1,
          points: 10,
          time_limit: 5
        }])
      });
    });
    
    await page.goto('/quizzes/1');
    await page.click('text=Start Quiz');
    await waitForPageLoad(page);
    
    // Should show time limit indicator
    await expect(page.locator('text=5s')).toBeVisible();
    await expect(page.locator('[data-testid="time-limit"]')).toBeVisible();
  });
});
