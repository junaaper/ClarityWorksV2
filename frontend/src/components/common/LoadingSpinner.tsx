import React from 'react';

interface Props {
  message?: string;
  fullScreen?: boolean;
}

const LoadingSpinner: React.FC<Props> = ({ message = 'Processing...', fullScreen = false }) => {
  const containerClass = fullScreen
    ? 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50'
    : 'flex flex-col items-center justify-center p-8';

  return (
    <div className={containerClass}>
      <div className="bg-white rounded-lg p-8 shadow-xl">
        <div className="flex flex-col items-center">
          {/* Spinner */}
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-500"></div>

          {/* Message */}
          <p className="mt-4 text-gray-700 font-medium">{message}</p>

          {/* Sub-message */}
          <p className="mt-2 text-sm text-gray-500">This may take a few moments...</p>
        </div>
      </div>
    </div>
  );
};

export default LoadingSpinner;
