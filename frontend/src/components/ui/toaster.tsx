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
        return <CheckCircle className="h-4 w-4 flex-shrink-0 text-green-500 self-center" />
      case "warning":
        return <AlertTriangle className="h-4 w-4 flex-shrink-0 text-yellow-500 self-center" />
      case "error":
      case "destructive":
        return <XCircle className="h-4 w-4 flex-shrink-0 text-accent-red self-center" />
      case "info":
      case "default":
        return <Info className="h-4 w-4 flex-shrink-0 text-blue-500 self-center" />
      default:
        return <Info className="h-4 w-4 flex-shrink-0 text-blue-500 self-center" />
    }
  }

  return (
    <ToastProvider>
      {toasts.map(function ({ id, title, description, action, variant, ...props }) {
        return (
          <Toast key={id} variant={variant} {...props}>
            <div className="flex items-center gap-2 w-full pr-4">
              {getToastIcon(variant)}
              <div className="grid gap-0.5 flex-1 min-w-0">
                {title && <ToastTitle>{title}</ToastTitle>}
                {description && (
                  <ToastDescription>{description}</ToastDescription>
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
