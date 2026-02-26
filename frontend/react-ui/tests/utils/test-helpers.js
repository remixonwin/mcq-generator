import { test as base } from '@playwright/test';

// Custom test fixtures with authentication
export const authenticatedPage = base.extend({
  page: async ({ page }, use) => {
    // Set authentication
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('auth_token', 'test-token');
      localStorage.setItem('user', JSON.stringify({
        id: 1,
        name: 'Test User',
        email: 'test@example.com'
      }));
    });
    await use(page);
  }
});

// Also export it as a regular test for backward compatibility
export const authenticatedTest = authenticatedPage;

export const test = base.extend({
  authenticatedPage: async ({ page, context }, use) => {
    // Login with test user
    await context.addCookies([
      {
        name: 'auth_token',
        value: 'test-token',
        domain: 'localhost',
        path: '/',
      },
    ]);
    
    // Set localStorage for authenticated state
    await page.goto('/login');
    await page.evaluate(() => {
      localStorage.setItem('auth_token', 'test-token');
      localStorage.setItem('user', JSON.stringify({
        id: 1,
        name: 'Test User',
        email: 'test@example.com'
      }));
    });
    
    await page.goto('/dashboard');
    await use(page);
  },
  
  mockApiResponse: async ({ page }, use) => {
    const mockResponses = [];
    
    await page.route('**/api/v1/**', async (route) => {
      const url = route.request().url();
      const method = route.request().method();
      
      // Find matching mock response
      const mock = mockResponses.find(m => 
        url.includes(m.path) && method === m.method
      );
      
      if (mock) {
        await route.fulfill({
          status: mock.status || 200,
          contentType: 'application/json',
          body: JSON.stringify(mock.response)
        });
      } else {
        await route.fallback();
      }
    });
    
    await use((path, method, response, status = 200) => {
      mockResponses.push({ path, method, response, status });
    });
  },
});

export const expect = base.expect;

// Common test utilities
export const waitForPageLoad = async (page) => {
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500); // Small delay for animations
};

export const fillForm = async (page, formData) => {
  for (const [selector, value] of Object.entries(formData)) {
    await page.fill(selector, value);
  }
};

export const submitForm = async (page, buttonSelector = 'button[type="submit"]') => {
  await page.click(buttonSelector);
  await waitForPageLoad(page);
};

export const createTestQuiz = async (page, quizData = {}) => {
  const defaultQuiz = {
    title: 'Test Quiz',
    description: 'A test quiz for E2E testing',
    category: 'Science',
    difficulty: 'medium',
    is_public: true,
    questions: [
      {
        question_text: 'What is 2 + 2?',
        question_type: 'multiple_choice',
        options: JSON.stringify(['3', '4', '5', '6']),
        correct_answer: 1,
        points: 10
      }
    ]
  };
  
  const finalQuizData = { ...defaultQuiz, ...quizData };
  
  // Mock the API response
  await page.evaluate((quiz) => {
    window.mockApiResponse('/api/v1/quizzes', 'POST', {
      id: 1,
      ...quiz,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    });
  }, finalQuizData);
  
  return finalQuizData;
};

export const navigateToQuizCreation = async (page) => {
  await page.goto('/dashboard');
  await page.click('text=Create New Quiz');
  await waitForPageLoad(page);
  await expect(page).toHaveURL(/\/quizzes\/create/);
};

export const navigateToQuizLibrary = async (page) => {
  await page.goto('/library');
  await waitForPageLoad(page);
  await expect(page).toHaveURL(/\/library/);
};

export const navigateToMyQuizzes = async (page) => {
  await page.goto('/my-quizzes');
  await waitForPageLoad(page);
  await expect(page).toHaveURL(/\/my-quizzes/);
};
