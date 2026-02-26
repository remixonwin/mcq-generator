import React from 'react';
import RegisterForm from '../components/auth/RegisterForm';
import AuthLayout from '../components/auth/AuthLayout';

const Register = () => {
  return (
    <AuthLayout 
      title="Join QuizMe Today"
      subtitle="Start creating engaging quizzes and transform your content into interactive learning experiences."
    >
      <RegisterForm />
    </AuthLayout>
  );
};

export default Register;
