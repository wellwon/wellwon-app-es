import * as React from "react"
import { cn } from "@/lib/utils"

export interface AutoResizeTextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  minHeight?: number;
  maxHeight?: number;
  onHeightChange?: (height: number) => void;
}

const AutoResizeTextarea = React.forwardRef<HTMLTextAreaElement, AutoResizeTextareaProps>(
  ({ className, minHeight = 24, maxHeight = 120, onHeightChange, ...props }, ref) => {
    const textareaRef = React.useRef<HTMLTextAreaElement>(null);
    const combinedRef = React.useCallback((node: HTMLTextAreaElement) => {
      textareaRef.current = node;
      if (typeof ref === 'function') {
        ref(node);
      } else if (ref) {
        ref.current = node;
      }
    }, [ref]);

    const adjustHeight = React.useCallback(() => {
      const textarea = textareaRef.current;
      if (textarea) {
        // When empty, use minHeight directly to avoid padding/line-height inflation
        if (!textarea.value) {
          textarea.style.height = `${minHeight}px`;
          if (onHeightChange) {
            onHeightChange(minHeight);
          }
          return;
        }

        textarea.style.height = 'auto';
        const scrollHeight = textarea.scrollHeight;
        const newHeight = Math.min(Math.max(scrollHeight, minHeight), maxHeight);
        textarea.style.height = `${newHeight}px`;

        if (onHeightChange) {
          onHeightChange(newHeight);
        }
      }
    }, [minHeight, maxHeight, onHeightChange]);

    React.useEffect(() => {
      adjustHeight();
    }, [props.value, adjustHeight]);

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      adjustHeight();
      if (props.onChange) {
        props.onChange(e);
      }
    };

    // Calculate vertical padding to center single line of text
    // text-sm = 14px, leading-5 = 20px line-height, so padding = (minHeight - 20) / 2
    // For minHeight=36: (36-20)/2 = 8px padding top and bottom
    const lineHeight = 20;
    const verticalPadding = Math.max(4, (minHeight - lineHeight) / 2);

    return (
      <textarea
        ref={combinedRef}
        className={cn(
          "flex w-full rounded-md border border-input bg-background px-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 resize-none overflow-y-auto scrollbar-hide transition-all duration-200",
          className
        )}
        style={{
          minHeight: `${minHeight}px`,
          maxHeight: `${maxHeight}px`,
          paddingTop: `${verticalPadding}px`,
          paddingBottom: `${verticalPadding}px`
        }}
        onChange={handleChange}
        rows={1}
        {...props}
      />
    )
  }
)
AutoResizeTextarea.displayName = "AutoResizeTextarea"

export { AutoResizeTextarea }