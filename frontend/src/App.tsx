import { useState } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { QueryTemplate } from './types';

function App() {
  const [selectedTemplate, setSelectedTemplate] = useState<QueryTemplate | null>(
    null
  );
  const [showInfoQueryBuilder, setShowInfoQueryBuilder] = useState(false);
  const [infoQueryTemplate, setInfoQueryTemplate] = useState<QueryTemplate | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [resetTrigger, setResetTrigger] = useState(0);

  const handleSelectTemplate = (template: QueryTemplate) => {
    // Check if it's a "상품/담보 설명" category template
    if (template.category === '상품/담보 설명') {
      setInfoQueryTemplate(template);
      setShowInfoQueryBuilder(true);
    } else {
      setSelectedTemplate(template);
    }
  };

  const handleCategoryChange = (category: string | null) => {
    // 카테고리 변경 시 이전 상태 초기화
    if (category !== selectedCategory) {
      setSelectedTemplate(null);
      setShowInfoQueryBuilder(false);
      setInfoQueryTemplate(null);
      setResetTrigger(prev => prev + 1);
    }
    setSelectedCategory(category);
  };

  const handleNewChat = () => {
    setSelectedTemplate(null);
    setShowInfoQueryBuilder(false);
    setInfoQueryTemplate(null);
    setSelectedCategory(null);
    setResetTrigger(prev => prev + 1);
  };

  const handleTemplateClear = () => {
    setSelectedTemplate(null);
  };

  const handleCloseInfoQueryBuilder = () => {
    setShowInfoQueryBuilder(false);
    setInfoQueryTemplate(null);
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        onSelectTemplate={handleSelectTemplate}
        onNewChat={handleNewChat}
        onCategoryChange={handleCategoryChange}
      />
      <ChatInterface
        selectedTemplate={selectedTemplate}
        onTemplateClear={handleTemplateClear}
        showInfoQueryBuilder={showInfoQueryBuilder}
        infoQueryTemplate={infoQueryTemplate}
        onCloseInfoQueryBuilder={handleCloseInfoQueryBuilder}
        selectedCategory={selectedCategory}
        resetTrigger={resetTrigger}
      />
    </div>
  );
}

export default App;
