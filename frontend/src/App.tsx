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
    setSelectedCategory(category);
  };

  const handleNewChat = () => {
    setSelectedTemplate(null);
    setShowInfoQueryBuilder(false);
    setInfoQueryTemplate(null);
    setSelectedCategory(null);
    // ChatInterface will handle clearing messages
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
      />
    </div>
  );
}

export default App;
