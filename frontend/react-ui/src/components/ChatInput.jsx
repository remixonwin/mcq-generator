import React, { useState } from 'react';
import QuizViewer from './QuizViewer';

const ChatInput = () => {
  const [inputText, setInputText] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [quizResult, setQuizResult] = useState(null);

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    setSelectedFile(file);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append('file', selectedFile);

    setIsUploading(true);
    try {
      // TODO: Replace with actual backend API endpoint
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        console.log('File uploaded successfully');
        // Handle successful upload
      } else {
        console.error('File upload failed');
      }
    } catch (error) {
      console.error('Error uploading file:', error);
    } finally {
      setIsUploading(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    
    if (!inputText.trim() && !selectedFile) return;

    try {
      // Determine the type of request based on input
      let requestData = {};
      let endpoint = '/api/generate-quiz';
      
      if (selectedFile) {
        // If file is selected, send file data
        const formData = new FormData();
        formData.append('file', selectedFile);
        if (inputText.trim()) {
          formData.append('prompt', inputText);
        }
        
        // For file uploads, we use multipart/form-data which is handled automatically by FormData
        const response = await fetch(endpoint, {
          method: 'POST',
          body: formData,
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('Quiz generation response:', result);
        setQuizResult(result);
      } else {
        // If only text is provided, send as JSON
        requestData = {
          prompt: inputText,
          type: 'text'
        };
        
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestData),
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('Quiz generation response:', result);
        setQuizResult(result);
      }
    } catch (error) {
      console.error('Error generating quiz:', error);
    }

    // Reset form
    setInputText('');
    setSelectedFile(null);
    const fileInput = document.getElementById('file-upload');
    if (fileInput) fileInput.value = '';
  };

  return (
    <div className="chat-input-container">
      <form onSubmit={handleSubmit} className="chat-form">
        <div className="input-group">
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Ask for a quiz by keyword, paste text content, or upload a document..."
            className="chat-textarea"
          />
        </div>
        
        <div className="file-input-group">
          <input
            type="file"
            id="file-upload"
            onChange={handleFileChange}
            accept=".pdf,.doc,.docx,.txt,.md"
            className="file-input"
          />
          <label htmlFor="file-upload" className="file-label">
            📎 Attach File
          </label>
          
          {selectedFile && (
            <div className="file-info">
              <span>Selected: {selectedFile.name}</span>
              <button 
                type="button" 
                onClick={() => {
                  setSelectedFile(null);
                  const fileInput = document.getElementById('file-upload');
                  if (fileInput) fileInput.value = '';
                }}
                className="remove-file-btn"
              >
                ✕
              </button>
            </div>
          )}
        </div>
        
        <div className="submit-section">
          <button 
            type="submit" 
            disabled={!inputText.trim() && !selectedFile}
            className="submit-btn"
          >
            Generate Quiz
          </button>
          
          {selectedFile && (
            <button 
              type="button" 
              onClick={handleUpload}
              disabled={isUploading}
              className="upload-btn"
            >
              {isUploading ? 'Uploading...' : 'Upload Only'}
            </button>
          )}
        </div>
      </form>
      {/* render quiz results if available */}
      {quizResult && (
        <div className="mt-8">
          <h2 className="text-xl font-bold mb-4">Generated Quiz</h2>
          <QuizViewer quiz={quizResult} />
        </div>
      )}
    </div>
  );
};

export default ChatInput;