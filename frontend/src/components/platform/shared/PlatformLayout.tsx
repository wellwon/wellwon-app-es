import React, { useCallback, useState } from 'react';
import { usePlatform } from '@/contexts/PlatformContext';
import SidebarMain from '../sidebar/SidebarMain';
import SidebarChat from '../sidebar/SidebarChat';
import SafeContentRenderer from './SafeContentRenderer';
import DeveloperPanel from '../developer/DeveloperPanel';
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable';
import { useIsMobile } from '@/hooks/use-mobile';

const STORAGE_KEY = 'ww:layout-panel-sizes';

const PlatformLayout = () => {
  const { activeSection, userTheme } = usePlatform();
  const isMobile = useIsMobile();

  // Load saved panel sizes from localStorage
  const [chatSidebarSize, setChatSidebarSize] = useState<number>(() => {
    if (typeof window === 'undefined') return 25;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        return parsed.chatSidebar ?? 25;
      }
    } catch (error) {
      console.warn('Failed to load panel sizes:', error);
    }
    return 25;
  });

  // Save panel sizes when changed
  const handlePanelResize = useCallback((sizes: number[]) => {
    if (sizes.length >= 2) {
      const newChatSize = sizes[0];
      setChatSidebarSize(newChatSize);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ chatSidebar: newChatSize }));
      } catch (error) {
        console.warn('Failed to save panel sizes:', error);
      }
    }
  }, []);

  // Mobile layout - no sidebars
  if (isMobile) {
    return (
      <div className={`h-screen bg-dark-gray flex overflow-hidden ${userTheme}`}>
        <div className="flex-1 flex flex-col min-w-0 relative bg-dark-gray">
          <SafeContentRenderer sectionId={activeSection} />
        </div>
        <DeveloperPanel />
      </div>
    );
  }

  return (
    <div className={`h-screen bg-dark-gray flex overflow-hidden ${userTheme}`}>
      {/* SidebarMain - fixed width, not resizable */}
      <div style={{ backgroundColor: '#2c2c33' }}>
        <SidebarMain />
      </div>

      {/* Resizable area: SidebarChat + Main Content */}
      {activeSection === 'chat' ? (
        <ResizablePanelGroup
          direction="horizontal"
          onLayout={handlePanelResize}
          className="flex-1"
        >
          {/* Chat Sidebar - resizable */}
          <ResizablePanel
            defaultSize={chatSidebarSize}
            minSize={15}
            maxSize={40}
            className="min-w-0"
          >
            <SidebarChat />
          </ResizablePanel>

          {/* Resize Handle */}
          <ResizableHandle />

          {/* Main Content */}
          <ResizablePanel
            defaultSize={100 - chatSidebarSize}
            minSize={40}
            className="min-w-0"
          >
            <div className="h-full flex flex-col relative bg-dark-gray">
              <SafeContentRenderer sectionId={activeSection} />
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      ) : (
        // Non-chat sections - no chat sidebar, full width content
        <div className="flex-1 flex flex-col min-w-0 relative bg-dark-gray">
          <SafeContentRenderer sectionId={activeSection} />
        </div>
      )}

      {/* Floating Developer Panel */}
      <DeveloperPanel />
    </div>
  );
};

export default PlatformLayout;