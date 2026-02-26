import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Brain, BookOpen, BarChart3, Settings, LogOut, User } from 'lucide-react';

const Dashboard = () => {
  const { user, logout, api } = useAuth();

  const handleLogout = async () => {
    await logout();
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-r from-primary-600 to-indigo-600 rounded-lg flex items-center justify-center">
                <Brain className="w-5 h-5 text-white" />
              </div>
              <h1 className="text-xl font-bold text-gray-900">QuizMe</h1>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center">
                  <User className="w-4 h-4 text-gray-600" />
                </div>
                <div className="hidden sm:block">
                  <p className="text-sm font-medium text-gray-900">{user?.name}</p>
                  <p className="text-xs text-gray-500">{user?.email}</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button className="p-2 text-gray-500 hover:text-gray-700 transition-colors">
                  <Settings className="w-5 h-5" />
                </button>
                <button
                  onClick={handleLogout}
                  className="p-2 text-gray-500 hover:text-gray-700 transition-colors"
                >
                  <LogOut className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome section */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Welcome back, {user?.name}!
          </h2>
          <p className="text-gray-600">
            Ready to create amazing quizzes? Let's get started.
          </p>
        </div>

        {/* Stats cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <BookOpen className="w-6 h-6 text-blue-600" />
              </div>
              <span className="text-2xl font-bold text-gray-900">12</span>
            </div>
            <p className="text-sm font-medium text-gray-900">Total Quizzes</p>
            <p className="text-xs text-gray-500">Created by you</p>
          </div>

          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <BarChart3 className="w-6 h-6 text-green-600" />
              </div>
              <span className="text-2xl font-bold text-gray-900">248</span>
            </div>
            <p className="text-sm font-medium text-gray-900">Total Responses</p>
            <p className="text-xs text-gray-500">Across all quizzes</p>
          </div>

          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                <Brain className="w-6 h-6 text-purple-600" />
              </div>
              <span className="text-2xl font-bold text-gray-900">89%</span>
            </div>
            <p className="text-sm font-medium text-gray-900">Avg. Score</p>
            <p className="text-xs text-gray-500">User performance</p>
          </div>

          <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-orange-100 rounded-lg flex items-center justify-center">
                <User className="w-6 h-6 text-orange-600" />
              </div>
              <span className="text-2xl font-bold text-gray-900">45</span>
            </div>
            <p className="text-sm font-medium text-gray-900">Active Users</p>
            <p className="text-xs text-gray-500">This month</p>
          </div>
        </div>

        {/* Quick actions */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-6">Quick Actions</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <button className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-left">
              <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
                <Brain className="w-5 h-5 text-primary-600" />
              </div>
              <div>
                <p className="font-medium text-gray-900">Create New Quiz</p>
                <p className="text-sm text-gray-500">Start from scratch or use AI</p>
              </div>
            </button>

            <button className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-left">
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                <BookOpen className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="font-medium text-gray-900">Browse Templates</p>
                <p className="text-sm text-gray-500">Use pre-made quiz templates</p>
              </div>
            </button>

            <button className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-left">
              <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                <BarChart3 className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="font-medium text-gray-900">View Analytics</p>
                <p className="text-sm text-gray-500">Track quiz performance</p>
              </div>
            </button>
          </div>
        </div>

        {/* Recent activity */}
        <div className="mt-8 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-6">Recent Activity</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-gray-100">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                  <span className="text-xs font-semibold text-green-600">✓</span>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">Quiz "JavaScript Basics" completed</p>
                  <p className="text-xs text-gray-500">2 hours ago</p>
                </div>
              </div>
              <span className="text-sm text-gray-500">85% score</span>
            </div>

            <div className="flex items-center justify-between py-3 border-b border-gray-100">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                  <span className="text-xs font-semibold text-blue-600">+</span>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">New quiz "React Fundamentals" created</p>
                  <p className="text-xs text-gray-500">5 hours ago</p>
                </div>
              </div>
              <span className="text-sm text-gray-500">12 questions</span>
            </div>

            <div className="flex items-center justify-between py-3">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center">
                  <span className="text-xs font-semibold text-purple-600">★</span>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">Quiz "Python Basics" published</p>
                  <p className="text-xs text-gray-500">1 day ago</p>
                </div>
              </div>
              <span className="text-sm text-gray-500">Public</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Dashboard;
