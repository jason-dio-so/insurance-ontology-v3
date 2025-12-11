import React, { useState } from 'react';
import { QueryTemplate } from '../types';
import { queryTemplates, categories } from '../data/queryTemplates';

interface SidebarProps {
  onSelectTemplate: (template: QueryTemplate) => void;
  onNewChat: () => void;
  onCategoryChange?: (category: string | null) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ onSelectTemplate, onCategoryChange }) => {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const handleCategorySelect = (category: string) => {
    setSelectedCategory(category);
    if (onCategoryChange) {
      onCategoryChange(category);
    }
  };

  const filteredTemplates = queryTemplates.filter((template) => {
    return !selectedCategory || template.category === selectedCategory;
  });

  return (
    <div className="w-80 bg-sidebar-bg text-white h-screen flex flex-col">
      {/* Categories */}
      <div className="px-4 pb-2 pt-4">
        <div className="text-xs text-gray-400 mb-2">카테고리</div>
        <div className="flex flex-col gap-2">
          {categories.map((category) => (
            <button
              key={category}
              onClick={() => handleCategorySelect(category)}
              className={`px-4 py-2 rounded-lg text-sm text-left transition-colors ${
                selectedCategory === category
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {category}
            </button>
          ))}
        </div>
      </div>

      {/* Template List */}
      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {selectedCategory ? (
          <div className="space-y-2">
            {filteredTemplates.map((template) => (
              <button
                key={template.id}
                onClick={() => onSelectTemplate(template)}
                className="w-full text-left p-3 rounded-lg hover:bg-gray-700 transition-colors duration-200 group"
              >
                <div className="flex items-start gap-2">
                  <div className="flex-shrink-0 mt-1">
                    <svg
                      className="w-4 h-4 text-gray-400 group-hover:text-blue-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                      />
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-white group-hover:text-blue-400">
                      {template.title}
                    </div>
                    <div className="text-xs text-gray-400 mt-1 line-clamp-2">
                      {template.description}
                    </div>
                    <div className="text-xs text-gray-500 mt-1 italic">
                      예: {template.example}
                    </div>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {template.tags.map((tag) => (
                        <span
                          key={tag}
                          className="px-2 py-0.5 bg-gray-800 text-gray-400 text-xs rounded"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="text-center text-gray-400 mt-8">
            <div className="text-4xl mb-2">📁</div>
            <div className="text-sm">카테고리를 선택해주세요</div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-700">
        <div className="text-xs text-gray-400 text-center">
          보험 온톨로지 AI v1.0
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
