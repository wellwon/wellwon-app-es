import React from 'react';
import ChatInfoPanel from './ChatInfoPanel';

// Мемоизированный компонент ChatInfoPanel
const ChatInfoPanelMemo = React.memo(() => {
  return <ChatInfoPanel />;
});

ChatInfoPanelMemo.displayName = 'ChatInfoPanelMemo';

export default ChatInfoPanelMemo;