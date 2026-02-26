import React from 'react';
import { Link } from 'react-router-dom';
import { Brain, BookOpen, Target, Zap } from 'lucide-react';

const AuthLayout = ({ children, title, subtitle }) => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 flex">
      {/* Left side - Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Logo */}
          <div className="text-center mb-8">
            <Link to="/" className="inline-flex items-center gap-2 group">
              <div className="w-10 h-10 bg-gradient-to-r from-primary-600 to-indigo-600 rounded-lg flex items-center justify-center group-hover:shadow-lg transition-shadow">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <span className="text-2xl font-bold text-gray-900">QuizMe</span>
            </Link>
          </div>

          {/* Form content */}
          {children}
        </div>
      </div>

      {/* Right side - Hero content */}
      <div className="hidden lg:flex lg:flex-1 lg:bg-gradient-to-br from-primary-600 to-indigo-700 relative overflow-hidden">
        {/* Background pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0 bg-grid-white/10 bg-grid-16"></div>
        </div>

        {/* Content */}
        <div className="relative z-10 flex flex-col justify-center px-12 py-16 text-white">
          <div className="max-w-lg">
            <h1 className="text-4xl font-bold mb-6">
              {title || 'Create Engaging Quizzes in Minutes'}
            </h1>
            <p className="text-xl text-blue-100 mb-8">
              {subtitle || 'Transform your content into interactive quizzes that captivate and educate your audience.'}
            </p>

            {/* Features */}
            <div className="space-y-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-white/10 rounded-lg flex items-center justify-center flex-shrink-0 backdrop-blur-sm">
                  <Zap className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold mb-1">Lightning Fast</h3>
                  <p className="text-blue-100">Generate comprehensive quizzes from any content in seconds</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-white/10 rounded-lg flex items-center justify-center flex-shrink-0 backdrop-blur-sm">
                  <BookOpen className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold mb-1">Smart Content Analysis</h3>
                  <p className="text-blue-100">AI-powered question generation from documents, text, or topics</p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-white/10 rounded-lg flex items-center justify-center flex-shrink-0 backdrop-blur-sm">
                  <Target className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold mb-1">Engaging Experience</h3>
                  <p className="text-blue-100">Interactive quizzes that make learning fun and effective</p>
                </div>
              </div>
            </div>

            {/* Testimonials */}
            <div className="mt-12 p-6 bg-white/10 rounded-lg backdrop-blur-sm">
              <blockquote className="text-lg italic text-blue-100 mb-3">
                "QuizMe transformed how we create educational content. Our students love the interactive quizzes!"
              </blockquote>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
                  <span className="text-sm font-semibold">JD</span>
                </div>
                <div>
                  <p className="font-semibold">Jane Doe</p>
                  <p className="text-sm text-blue-100">Education Director</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Floating elements */}
        <div className="absolute top-20 right-20 w-20 h-20 bg-white/5 rounded-full backdrop-blur-sm animate-pulse"></div>
        <div className="absolute bottom-20 left-20 w-32 h-32 bg-white/5 rounded-full backdrop-blur-sm animate-pulse delay-1000"></div>
        <div className="absolute top-1/2 right-1/3 w-16 h-16 bg-white/5 rounded-full backdrop-blur-sm animate-pulse delay-500"></div>
      </div>
    </div>
  );
};

export default AuthLayout;
