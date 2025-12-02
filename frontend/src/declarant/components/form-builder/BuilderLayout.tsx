// =============================================================================
// BuilderLayout - 3-колоночный layout для конструктора форм
// =============================================================================

import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';

interface BuilderLayoutProps {
  leftPanel: React.ReactNode;
  canvas: React.ReactNode;
  rightPanel: React.ReactNode;
  header?: React.ReactNode;
  footer?: React.ReactNode;
  isDark: boolean;
  leftPanelWidth?: number;
  rightPanelWidth?: number;
  onPanelResize?: (left: number, right: number) => void;
}

export const BuilderLayout: React.FC<BuilderLayoutProps> = ({
  leftPanel,
  canvas,
  rightPanel,
  header,
  footer,
  isDark,
  leftPanelWidth = 280,
  rightPanelWidth = 320,
  onPanelResize,
}) => {
  const [leftWidth, setLeftWidth] = useState(leftPanelWidth);
  const [rightWidth, setRightWidth] = useState(rightPanelWidth);
  const [isResizingLeft, setIsResizingLeft] = useState(false);
  const [isResizingRight, setIsResizingRight] = useState(false);

  const handleLeftMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingLeft(true);
  }, []);

  const handleRightMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingRight(true);
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (isResizingLeft) {
        const newWidth = Math.max(200, Math.min(400, e.clientX));
        setLeftWidth(newWidth);
        onPanelResize?.(newWidth, rightWidth);
      }
      if (isResizingRight) {
        const newWidth = Math.max(250, Math.min(450, window.innerWidth - e.clientX));
        setRightWidth(newWidth);
        onPanelResize?.(leftWidth, newWidth);
      }
    },
    [isResizingLeft, isResizingRight, leftWidth, rightWidth, onPanelResize]
  );

  const handleMouseUp = useCallback(() => {
    setIsResizingLeft(false);
    setIsResizingRight(false);
  }, []);

  React.useEffect(() => {
    if (isResizingLeft || isResizingRight) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isResizingLeft, isResizingRight, handleMouseMove, handleMouseUp]);

  const theme = isDark
    ? {
        bg: 'bg-[#1a1a1e]',
        border: 'border-white/10',
        panelBg: 'bg-[#232328]',
        resizer: 'bg-white/5 hover:bg-white/10',
        resizerActive: 'bg-accent-red/50',
      }
    : {
        bg: 'bg-[#f4f4f4]',
        border: 'border-gray-200',
        panelBg: 'bg-white',
        resizer: 'bg-gray-100 hover:bg-gray-200',
        resizerActive: 'bg-accent-red/50',
      };

  return (
    <div className={cn('flex flex-col h-full', theme.bg)}>
      {/* Header */}
      {header && (
        <div className={cn('border-b', theme.border)}>
          {header}
        </div>
      )}

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Panel */}
        <div
          className={cn('flex-shrink-0 overflow-hidden', theme.panelBg, 'border-r', theme.border)}
          style={{ width: leftWidth }}
        >
          <div className="h-full overflow-y-auto">
            {leftPanel}
          </div>
        </div>

        {/* Left Resizer */}
        <div
          className={cn(
            'w-1.5 cursor-col-resize transition-colors group relative',
            isResizingLeft ? theme.resizerActive : theme.resizer
          )}
          onMouseDown={handleLeftMouseDown}
        >
          {/* Wider hit area */}
          <div className="absolute inset-y-0 -left-1 -right-1 cursor-col-resize" />
          {/* Visual indicator on hover */}
          <div className={cn(
            'absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-8 rounded-full opacity-0 group-hover:opacity-100 transition-opacity',
            isDark ? 'bg-white/30' : 'bg-gray-400'
          )} />
        </div>

        {/* Canvas (center) */}
        <div className="flex-1 overflow-hidden">
          <div className="h-full overflow-y-auto">
            {canvas}
          </div>
        </div>

        {/* Right Resizer */}
        <div
          className={cn(
            'w-1.5 cursor-col-resize transition-colors group relative',
            isResizingRight ? theme.resizerActive : theme.resizer
          )}
          onMouseDown={handleRightMouseDown}
        >
          {/* Wider hit area */}
          <div className="absolute inset-y-0 -left-1 -right-1 cursor-col-resize" />
          {/* Visual indicator on hover */}
          <div className={cn(
            'absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-8 rounded-full opacity-0 group-hover:opacity-100 transition-opacity',
            isDark ? 'bg-white/30' : 'bg-gray-400'
          )} />
        </div>

        {/* Right Panel */}
        <div
          className={cn('flex-shrink-0 overflow-hidden', theme.panelBg, 'border-l', theme.border)}
          style={{ width: rightWidth }}
        >
          <div className="h-full overflow-y-auto">
            {rightPanel}
          </div>
        </div>
      </div>

      {/* Footer */}
      {footer && (
        <div className={cn('border-t', theme.border)}>
          {footer}
        </div>
      )}
    </div>
  );
};

export default BuilderLayout;
