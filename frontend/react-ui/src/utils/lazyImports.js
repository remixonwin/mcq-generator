import { lazy } from 'react';

// Lazy load components for better performance
export const LazyDashboard = lazy(() => import('../pages/Dashboard').then(module => ({ default: module.Dashboard })));
export const LazyCreateQuiz = lazy(() => import('../pages/CreateQuiz').then(module => ({ default: module.CreateQuiz })));
export const LazyQuizLibrary = lazy(() => import('../pages/QuizLibrary').then(module => ({ default: module.QuizLibrary })));
export const LazyTakeQuiz = lazy(() => import('../pages/TakeQuiz').then(module => ({ default: module.TakeQuiz })));
export const LazyMyQuizzes = lazy(() => import('../pages/MyQuizzes').then(module => ({ default: module.MyQuizzes })));
export const LazyLogin = lazy(() => import('../pages/Login').then(module => ({ default: module.Login })));
export const LazyRegister = lazy(() => import('../pages/Register').then(module => ({ default: module.Register })));

// Lazy load heavy components
export const LazyQuizEditor = lazy(() => import('../components/QuizEditor').then(module => ({ default: module.default })));
export const LazyQuestionBank = lazy(() => import('../components/QuestionBank').then(module => ({ default: module.default })));
export const LazyAnalytics = lazy(() => import('../components/Analytics').then(module => ({ default: module.default })));

// Lazy load chart components
export const LazyChart = lazy(() => import('../components/Chart').then(module => ({ default: module.default })));
export const LazyQuizStats = lazy(() => import('../components/QuizStats').then(module => ({ default: module.default })));

// Preload critical components
export const preloadCriticalComponents = () => {
  // Preload the most commonly used components
  import('../pages/Dashboard');
  import('../pages/QuizLibrary');
  import('../pages/TakeQuiz');
};
