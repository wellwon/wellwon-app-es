
import React, { useCallback, useEffect, useState } from 'react';
import { usePlatform } from '@/contexts/PlatformContext';
import ChatNavigationBar from './core/ChatNavigationBar';
import AdminTabMenu from './services/AdminTabMenu';
import ChatInterface from './core/ChatInterface';
import AdminUnifiedSidebar from './sidebars/AdminUnifiedSidebar';
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable';

const STORAGE_KEY = 'ww:chat-panel-sizes';

const ChatContent: React.FC = () => {
  const { isDeveloper } = usePlatform();

  // Load saved panel sizes from localStorage
  const [rightSidebarSize, setRightSidebarSize] = useState<number>(() => {
    if (typeof window === 'undefined') return 25;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        return parsed.rightSidebar ?? 25;
      }
    } catch (error) {
      console.warn('Failed to load panel sizes:', error);
    }
    return 25;
  });

  // Save panel sizes when changed
  const handlePanelResize = useCallback((sizes: number[]) => {
    // sizes[0] is main content, sizes[1] is right sidebar
    if (sizes.length >= 2) {
      const newRightSize = sizes[1];
      setRightSidebarSize(newRightSize);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ rightSidebar: newRightSize }));
      } catch (error) {
        console.warn('Failed to save panel sizes:', error);
      }
    }
  }, []);

  const renderTabMenu = () => {
    return <AdminTabMenu />;
  };

  return (
    <div className="h-full flex">
      <ResizablePanelGroup
        direction="horizontal"
        onLayout={handlePanelResize}
        className="h-full"
      >
        {/* Main Chat Area */}
        <ResizablePanel
          defaultSize={100 - rightSidebarSize}
          minSize={40}
          className="flex flex-col min-w-0"
        >
          {renderTabMenu()}
          <ChatNavigationBar />
          <div className="flex-1 min-h-0 overflow-hidden">
            <ChatInterface />
          </div>
        </ResizablePanel>

        {/* Resize Handle */}
        <ResizableHandle />

        {/* Sidebar - always visible */}
        <ResizablePanel
          defaultSize={rightSidebarSize}
          minSize={15}
          maxSize={50}
          className="min-w-0"
        >
          <AdminUnifiedSidebar />
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
};

export default ChatContent;
