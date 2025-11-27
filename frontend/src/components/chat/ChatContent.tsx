
import React from 'react';
import { usePlatform } from '@/contexts/PlatformContext';
import ChatNavigationBar from './core/ChatNavigationBar';
import AdminTabMenu from './services/AdminTabMenu';
import ChatInterface from './core/ChatInterface';
import AdminUnifiedSidebar from './sidebars/AdminUnifiedSidebar';
const ChatContent: React.FC = () => {
  const { isDeveloper } = usePlatform();

  const renderTabMenu = () => {
    return <AdminTabMenu />;
  };

  const renderSidebar = () => {
    return <AdminUnifiedSidebar />;
  };

  return (
    <div className="h-full flex">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {renderTabMenu()}
        <ChatNavigationBar />
        <div className="flex-1 min-h-0">
          <ChatInterface />
        </div>
      </div>
      
      {/* Sidebar - always visible */}
      {renderSidebar()}
    </div>
  );
};

export default ChatContent;
