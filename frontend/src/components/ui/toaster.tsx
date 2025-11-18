import { useToast } from "@/hooks/use-toast"
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast"
import { CheckCircle, AlertTriangle, Info, XCircle } from "lucide-react"

export function Toaster() {
  const { toasts } = useToast()

  const getToastIcon = (variant?: string) => {
    switch (variant) {
      case "success":
        return <CheckCircle className="h-8 w-8 flex-shrink-0 text-green-500 self-center" />
      case "warning":
        return <AlertTriangle className="h-8 w-8 flex-shrink-0 text-yellow-500 self-center" />
      case "error":
      case "destructive":
        return <XCircle className="h-8 w-8 flex-shrink-0 text-accent-red self-center" />
      case "info":
      case "default":
        return <Info className="h-8 w-8 flex-shrink-0 text-blue-500 self-center" />
      default:
        return <Info className="h-8 w-8 flex-shrink-0 text-blue-500 self-center" />
    }
  }

  return (
    <ToastProvider>
      {toasts.map(function ({ id, title, description, action, variant, ...props }) {
        return (
          <Toast key={id} variant={variant} {...props}>
            <div className="flex items-start gap-3 w-full pr-6">
              {getToastIcon(variant)}
              <div className="grid gap-1 flex-1 min-w-0">
                {title && <ToastTitle className="text-base font-medium">{title}</ToastTitle>}
                {description && (
                  <ToastDescription className="text-sm leading-relaxed">{description}</ToastDescription>
                )}
              </div>
            </div>
            {action}
            <ToastClose />
          </Toast>
        )
      })}
      <ToastViewport />
    </ToastProvider>
  )
}
