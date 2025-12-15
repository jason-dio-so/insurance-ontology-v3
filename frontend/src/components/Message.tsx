import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Message as MessageType } from '../types';
import ComparisonTable from './ComparisonTable';

interface MessageProps {
  message: MessageType;
  onRetry?: () => void;
}

const Message: React.FC<MessageProps> = ({ message, onRetry }) => {
  const isUser = message.role === 'user';
  const isError = message.isError;

  return (
    <div
      className={`py-6 px-4 ${
        isUser ? 'bg-user-msg' : isError ? 'bg-red-900/20' : 'bg-assistant-msg'
      }`}
    >
      <div className="max-w-4xl mx-auto flex gap-6">
        {/* Avatar */}
        <div className="flex-shrink-0">
          <div
            className={`w-8 h-8 rounded-sm flex items-center justify-center ${
              isUser ? 'bg-blue-600' : isError ? 'bg-red-600' : 'bg-green-600'
            }`}
          >
            {isUser ? (
              <svg
                className="w-5 h-5 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                />
              </svg>
            ) : isError ? (
              <svg
                className="w-5 h-5 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            ) : (
              <svg
                className="w-5 h-5 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                />
              </svg>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="prose prose-invert max-w-none">
            <ReactMarkdown
              components={{
                // Custom styles for markdown elements
                h1: ({ children }) => (
                  <h1 className="text-2xl font-bold mb-4 text-white">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-xl font-bold mb-3 mt-6 text-white">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-lg font-semibold mb-2 mt-4 text-white">
                    {children}
                  </h3>
                ),
                p: ({ children }) => (
                  <p className="mb-4 text-gray-300 leading-relaxed">
                    {children}
                  </p>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc list-inside mb-4 text-gray-300 space-y-1">
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal list-inside mb-4 text-gray-300 space-y-1">
                    {children}
                  </ol>
                ),
                li: ({ children }) => (
                  <li className="text-gray-300">{children}</li>
                ),
                strong: ({ children }) => (
                  <strong className="font-semibold text-white">
                    {children}
                  </strong>
                ),
                code: ({ children }) => (
                  <code className="bg-gray-700 px-1.5 py-0.5 rounded text-sm text-blue-300">
                    {children}
                  </code>
                ),
                pre: ({ children }) => (
                  <pre className="bg-gray-900 p-4 rounded-lg overflow-x-auto mb-4">
                    {children}
                  </pre>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Comparison Table */}
          {message.comparisonTable && (
            <ComparisonTable data={message.comparisonTable} />
          )}

          {/* Sources */}
          {message.sources && message.sources.length > 0 && (
            <div className="mt-6 pt-4 border-t border-gray-700">
              <div className="text-sm font-medium text-gray-400 mb-3">
                📄 참고 자료
              </div>
              <div className="space-y-2">
                {message.sources.map((source, index) => (
                  <div
                    key={index}
                    className="text-sm text-gray-400 bg-gray-800 p-3 rounded-lg"
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-blue-400 font-medium">
                        [{index + 1}]
                      </span>
                      <div className="flex-1">
                        <div className="text-white font-medium">
                          {source.company} - {source.product}
                        </div>
                        <div className="mt-1 text-gray-400 text-xs">
                          {source.clause}
                        </div>
                        {source.docType && (
                          <div className="mt-1 text-gray-500 text-xs">
                            문서 타입: {source.docType}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error Retry Button */}
          {isError && onRetry && (
            <button
              onClick={onRetry}
              className="mt-4 px-4 py-2 bg-red-600 text-white text-sm rounded hover:bg-red-700 transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              다시 시도
            </button>
          )}

          {/* Timestamp */}
          <div className="mt-4 text-xs text-gray-500">
            {message.timestamp.toLocaleTimeString('ko-KR', {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Message;
