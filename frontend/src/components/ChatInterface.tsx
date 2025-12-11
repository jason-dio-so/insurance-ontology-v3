import React, { useState, useRef, useEffect } from 'react';
import { Message as MessageType, QueryTemplate } from '../types';
import Message from './Message';
import { hybridSearch } from '../services/api';
import InfoQueryBuilder from './InfoQueryBuilder';
import { categoryMetadata } from '../data/queryTemplates';

interface ChatInterfaceProps {
  selectedTemplate: QueryTemplate | null;
  onTemplateClear: () => void;
  showInfoQueryBuilder?: boolean;
  infoQueryTemplate?: QueryTemplate | null;
  onCloseInfoQueryBuilder?: () => void;
  selectedCategory?: string | null;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  selectedTemplate,
  onTemplateClear,
  showInfoQueryBuilder = false,
  infoQueryTemplate = null,
  onCloseInfoQueryBuilder,
  selectedCategory = null,
}) => {
  const [messages, setMessages] = useState<MessageType[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [lastCoverage, setLastCoverage] = useState<string | null>(null);
  const [showReturnButton, setShowReturnButton] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-fill input and save template when selected
  const [currentTemplate, setCurrentTemplate] = useState<QueryTemplate | null>(null);

  useEffect(() => {
    if (selectedTemplate) {
      setInput(selectedTemplate.example);
      setCurrentTemplate(selectedTemplate);
      inputRef.current?.focus();
      onTemplateClear();
    }
  }, [selectedTemplate, onTemplateClear]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: MessageType = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await hybridSearch({
        query: userMessage.content,
        lastCoverage: lastCoverage || undefined,
        templateId: currentTemplate?.id,
        searchParams: currentTemplate?.searchParams,
      });

      const assistantMessage: MessageType = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.answer,
        timestamp: new Date(),
        comparisonTable: response.comparisonTable,
        sources: response.sources,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Update last coverage for context
      if (response.coverage) {
        setLastCoverage(response.coverage);
      }
    } catch (error) {
      console.error('Error calling API:', error);

      const errorMessage: MessageType = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content:
          '죄송합니다. 오류가 발생했습니다. 잠시 후 다시 시도해주세요.\n\n' +
          '오류 상세: ' +
          (error instanceof Error ? error.message : String(error)),
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setLastCoverage(null);
    setInput('');
    setCurrentTemplate(null);  // 템플릿도 초기화
    setShowReturnButton(false);  // 처음으로 버튼 숨기기
  };

  const handleInfoQuerySubmit = async (query: string, templateId: string) => {
    // Create user message
    const userMessage: MessageType = {
      id: Date.now().toString(),
      role: 'user',
      content: query,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await hybridSearch({
        query: query,
        lastCoverage: lastCoverage || undefined,
        templateId: templateId,
      });

      const assistantMessage: MessageType = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.answer,
        timestamp: new Date(),
        comparisonTable: response.comparisonTable,
        sources: response.sources,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Update last coverage for context
      if (response.coverage) {
        setLastCoverage(response.coverage);
      }

      // 조회 완료 후 "처음으로" 버튼 표시
      setShowReturnButton(true);
    } catch (error) {
      console.error('Error calling API:', error);

      const errorMessage: MessageType = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content:
          '죄송합니다. 오류가 발생했습니다. 잠시 후 다시 시도해주세요.\n\n' +
          '오류 상세: ' +
          (error instanceof Error ? error.message : String(error)),
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, errorMessage]);

      // 에러 발생 시에도 "처음으로" 버튼 표시
      setShowReturnButton(true);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-screen bg-chat-bg">
      {/* Header */}
      <div className="bg-sidebar-bg border-b border-gray-700 px-6 py-4 flex items-center justify-between">
        <h1 className="text-white text-lg font-semibold">
          보험 온톨로지 AI 챗봇
        </h1>
        {messages.length > 0 && (
          <button
            onClick={handleNewChat}
            className="text-gray-400 hover:text-white transition-colors text-sm"
          >
            대화 초기화
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-2xl px-4">
              <div className="text-4xl mb-4">💬</div>
              <h2 className="text-2xl font-bold text-white mb-2">
                보험 온톨로지 AI에 오신 것을 환영합니다
              </h2>
              <p className="text-gray-400 mb-6">
                왼쪽에서 질문 템플릿을 선택하거나, 아래에 자유롭게 질문해주세요.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-left">
                {categoryMetadata.map((category) => (
                  <div key={category.name} className="bg-gray-800 p-4 rounded-lg">
                    <div className={`${category.colorClass} font-medium mb-2`}>
                      {category.icon} {category.name}
                    </div>
                    <div className="text-sm text-gray-400">
                      {category.description}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <Message key={message.id} message={message} />
            ))}
            {isLoading && (
              <div className="py-6 px-4 bg-assistant-msg">
                <div className="max-w-4xl mx-auto flex gap-6">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 rounded-sm flex items-center justify-center bg-green-600">
                      <svg
                        className="w-5 h-5 text-white animate-spin"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-gray-300">
                      답변을 생성하고 있습니다...
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-gray-700 bg-sidebar-bg p-4">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                messages.length === 0
                  ? "왼쪽에서 카테고리를 선택해주세요"
                  : showReturnButton
                  ? "위의 '대화 초기화' 버튼을 눌러주세요"
                  : selectedCategory === '상품/담보 설명'
                  ? "왼쪽에서 조회할 정보를 선택해주세요"
                  : "질문을 입력하세요... (Shift+Enter로 줄바꿈)"
              }
              className="w-full bg-gray-700 text-white rounded-lg px-4 py-3 pr-12 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              rows={3}
              disabled={messages.length === 0 || isLoading || showReturnButton || selectedCategory === '상품/담보 설명'}
            />
            <button
              type="submit"
              disabled={messages.length === 0 || !input.trim() || isLoading || showReturnButton || selectedCategory === '상품/담보 설명'}
              className="absolute right-2 bottom-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg p-2 transition-colors duration-200"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                />
              </svg>
            </button>
          </div>
          <div className="mt-2 text-xs text-gray-500 text-center">
            Enter로 전송 • Shift+Enter로 줄바꿈
          </div>
        </form>
      </div>

      {/* InfoQueryBuilder Modal */}
      {showInfoQueryBuilder && onCloseInfoQueryBuilder && (
        <InfoQueryBuilder
          onQuerySubmit={handleInfoQuerySubmit}
          onClose={onCloseInfoQueryBuilder}
          preselectedInfoType={infoQueryTemplate?.id}
        />
      )}
    </div>
  );
};

export default ChatInterface;
