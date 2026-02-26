// Mock quiz data for testing
export const mockQuizzes = [
  {
    id: 1,
    title: 'Basic Mathematics Quiz',
    description: 'Test your basic math skills with this fun quiz',
    category: 'Mathematics',
    difficulty: 'easy',
    is_public: true,
    question_count: 5,
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z',
    created_by: 1
  },
  {
    id: 2,
    title: 'World Geography Challenge',
    description: 'Explore countries, capitals, and geographical features',
    category: 'Geography',
    difficulty: 'medium',
    is_public: true,
    question_count: 10,
    created_at: '2024-01-16T14:30:00Z',
    updated_at: '2024-01-16T14:30:00Z',
    created_by: 2
  },
  {
    id: 3,
    title: 'Advanced Physics',
    description: 'Complex physics concepts and problem-solving',
    category: 'Science',
    difficulty: 'hard',
    is_public: false,
    question_count: 8,
    created_at: '2024-01-17T09:15:00Z',
    updated_at: '2024-01-17T09:15:00Z',
    created_by: 1
  }
];

// Mock questions for testing
export const mockQuestions = [
  {
    id: 1,
    quiz_id: 1,
    question_text: 'What is 15 + 27?',
    question_type: 'multiple_choice',
    options: JSON.stringify(['40', '41', '42', '43']),
    correct_answer: 2,
    points: 10,
    time_limit: 30
  },
  {
    id: 2,
    quiz_id: 1,
    question_text: 'What is the capital of France?',
    question_type: 'multiple_choice',
    options: JSON.stringify(['London', 'Berlin', 'Paris', 'Madrid']),
    correct_answer: 2,
    points: 10,
    time_limit: 20
  },
  {
    id: 3,
    quiz_id: 1,
    question_text: 'Is the Earth round?',
    question_type: 'true_false',
    options: JSON.stringify(['True', 'False']),
    correct_answer: 0,
    points: 5,
    time_limit: 10
  }
];

// Mock quiz attempts and responses
export const mockQuizAttempt = {
  id: 1,
  quiz_id: 1,
  user_id: 1,
  started_at: '2024-01-18T10:00:00Z',
  completed_at: '2024-01-18T10:05:00Z',
  score: 80,
  total_possible: 100,
  responses: [
    {
      question_id: 1,
      selected_answer: '42',
      is_correct: true,
      time_taken: 15
    },
    {
      question_id: 2,
      selected_answer: 'Paris',
      is_correct: true,
      time_taken: 12
    },
    {
      question_id: 3,
      selected_answer: 'True',
      is_correct: true,
      time_taken: 5
    }
  ]
};

// Mock quiz statistics
export const mockQuizStats = {
  total_attempts: 25,
  average_score: 75.5,
  completion_rate: 92.0,
  average_time: 180, // seconds
  difficulty_distribution: {
    easy: 10,
    medium: 12,
    hard: 3
  },
  category_performance: {
    Mathematics: 85.0,
    Geography: 78.5,
    Science: 72.0
  }
};

// Test users
export const testUsers = [
  {
    id: 1,
    name: 'Test User',
    email: 'test@example.com',
    password: 'password123'
  },
  {
    id: 2,
    name: 'Admin User',
    email: 'admin@example.com',
    password: 'admin123'
  }
];

// Quiz creation test data
export const quizCreationTestData = {
  validQuiz: {
    title: 'E2E Test Quiz',
    description: 'This is a quiz created during E2E testing',
    category: 'Science',
    difficulty: 'medium',
    is_public: true
  },
  invalidQuiz: {
    title: '', // Empty title should fail validation
    description: 'This quiz has no title',
    category: 'Science',
    difficulty: 'medium',
    is_public: true
  },
  questions: [
    {
      question_text: 'What is the chemical symbol for water?',
      question_type: 'multiple_choice',
      options: JSON.stringify(['H2O', 'CO2', 'O2', 'N2']),
      correct_answer: 0,
      points: 10
    },
    {
      question_text: 'Is the sun a star?',
      question_type: 'true_false',
      options: JSON.stringify(['True', 'False']),
      correct_answer: 0,
      points: 5
    }
  ]
};

// Categories for testing
export const categories = [
  'Science', 'Mathematics', 'History', 'Geography', 'Literature',
  'Technology', 'Sports', 'Music', 'Art', 'General Knowledge'
];

// Difficulty levels for testing
export const difficulties = ['easy', 'medium', 'hard'];
