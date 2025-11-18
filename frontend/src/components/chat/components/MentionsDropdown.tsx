import React, { useLayoutEffect, useState } from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

interface MentionCandidate {
  id: string;
  name: string;
  username: string;
  roleLabel?: string;
  avatarUrl?: string;
  group: 'manager' | 'telegram';
}

interface MentionsDropdownProps {
  open: boolean;
  anchorRef: React.RefObject<HTMLElement>;
  query: string;
  items: MentionCandidate[];
  highlightedIndex: number;
  onSelect: (index: number) => void;
  onHover: (index: number) => void;
  onRequestClose: () => void;
  isLoading?: boolean;
  offsetAboveAnchor?: number;
}

export const MentionsDropdown: React.FC<MentionsDropdownProps> = ({
  open,
  anchorRef,
  query,
  items,
  highlightedIndex,
  onSelect,
  onHover,
  onRequestClose,
  isLoading = false,
  offsetAboveAnchor = 0
}) => {
  const [position, setPosition] = useState<{
    top?: number;
    bottom?: number;
    left: number;
    width: number;
    flipUp: boolean;
  }>({ left: 0, width: 320, flipUp: false });

  // ВАЖНО: useMemo должен быть всегда вызван, до любых условных return
  const groupedItems = React.useMemo(() => {
    const groups: { title: string; items: Array<MentionCandidate & { globalIndex: number }> }[] = [];
    
    let globalIndex = 0;
    const managers = items.filter(item => item.group === 'manager');
    const telegramUsers = items.filter(item => item.group === 'telegram');

    // Telegram пользователи СВЕРХУ
    if (telegramUsers.length > 0) {
      groups.push({
        title: 'Telegram пользователи',
        items: telegramUsers.map(item => ({ ...item, globalIndex: globalIndex++ }))
      });
    }

    // Менеджеры СНИЗУ
    if (managers.length > 0) {
      groups.push({
        title: 'Менеджеры',
        items: managers.map(item => ({ ...item, globalIndex: globalIndex++ }))
      });
    }

    return groups;
  }, [items]);

  useLayoutEffect(() => {
    if (!open || !anchorRef.current) return;

    const anchor = anchorRef.current;
    const rect = anchor.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    const dropdownHeight = Math.min(320, items.length * 36 + 60); // примерная высота
    const spaceBelow = viewportHeight - rect.bottom - 8; // 8px отступ
    const spaceAbove = rect.top - 8;
    
    const shouldFlipUp = spaceBelow < dropdownHeight && spaceAbove > spaceBelow;
    
    setPosition({
      left: rect.left,
      width: rect.width,
      ...(shouldFlipUp 
        ? { bottom: viewportHeight - rect.top + 8 + offsetAboveAnchor }
        : { top: rect.bottom + 8 }
      ),
      flipUp: shouldFlipUp
    });
  }, [open, items.length, anchorRef, offsetAboveAnchor]);

  if (!open || !anchorRef.current) {
    return null;
  }

  const dropdownStyle: React.CSSProperties = {
    position: 'fixed',
    left: position.left,
    width: position.width,
    zIndex: 60,
    ...(position.top !== undefined ? { top: position.top } : { bottom: position.bottom }),
  };

  // Show loading skeleton while loading
  if (isLoading) {
    return (
      <div 
        style={dropdownStyle}
        className="bg-[#2b2b30] border border-white/10 shadow-xl rounded-lg p-3"
      >
        <div className="space-y-2">
          <Skeleton className="h-4 w-24 bg-white/10" />
          {[...Array(3)].map((_, i) => (
            <div key={i} className="flex items-center gap-2">
              <Skeleton className="h-5 w-5 rounded-full bg-white/10" />
              <Skeleton className="h-4 flex-1 bg-white/10" />
              <Skeleton className="h-4 w-16 bg-white/10" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div 
        style={dropdownStyle}
        className="bg-[#2b2b30] border border-white/10 shadow-xl rounded-lg p-3"
      >
        <div className="text-xs text-muted-foreground text-center">
          Не найдено
        </div>
      </div>
    );
  }

  return (
    <div 
      style={dropdownStyle}
      className="bg-[#2b2b30] border border-white/10 shadow-xl rounded-lg max-h-80 overflow-y-auto"
    >
      {groupedItems.map((group, groupIndex) => (
        <div key={group.title} className={cn("p-1", groupIndex > 0 && "border-t border-white/5")}>
          <div className="px-2 py-1 text-xs text-muted-foreground/80 font-medium">
            {group.title}
          </div>
          {group.items.map((item) => (
            <div
              key={item.id}
              className={cn(
                "flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors h-8",
                highlightedIndex === item.globalIndex && "bg-white/10"
              )}
              onClick={() => onSelect(item.globalIndex)}
              onMouseEnter={() => onHover(item.globalIndex)}
            >
              {/* Показываем аватар для ВСЕХ пользователей */}
              <Avatar className="w-5 h-5">
                <AvatarImage src={item.avatarUrl} />
                <AvatarFallback className="text-xs">
                  {item.name.charAt(0).toUpperCase()}
                </AvatarFallback>
              </Avatar>
              
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 overflow-hidden">
                  <span className="text-sm text-foreground truncate">
                    {item.name}
                  </span>
                  {item.roleLabel && (
                    <Badge variant="outline" className="text-xs px-1 py-0 h-4 shrink-0 bg-white/10 border-white/20 text-white/60 hover:bg-white/15">
                      {item.roleLabel}
                    </Badge>
                  )}
                </div>
              </div>
              
              <span className="text-xs text-white/60 shrink-0">
                @{item.username}
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};