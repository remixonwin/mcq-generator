import React from 'react';
import LoginForm from '../components/auth/LoginForm';
import AuthLayout from '../components/auth/AuthLayout';

const Login = () => {
  return (
    <AuthLayout 
      title="Welcome Back to QuizMe"
      subtitle="Sign in to continue creating amazing quizzes and managing your content."
    >
      <LoginForm />
    </AuthLayout>
  );
};

export default Login;
