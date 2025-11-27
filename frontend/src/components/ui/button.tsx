
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-accent-red text-white hover:bg-accent-red/90 shadow-sm",
        destructive: "bg-gray-600 text-white hover:bg-gray-700 hover:scale-105 transition-all",
        outline: "border-2 border-accent-red bg-dark-gray/40 text-accent-red hover:bg-accent-red hover:text-white backdrop-blur-sm",
        secondary: "bg-white/5 text-gray-300 border border-white/10 hover:bg-white/10 hover:text-white hover:border-white/20 hover:scale-105 transition-all",
        ghost: "bg-white/5 text-gray-300 border border-white/10 hover:bg-white/10 hover:border-white/20 hover:scale-105 transition-all",
        link: "text-accent-red underline-offset-4 hover:underline",
        accent: "bg-accent-red text-white hover:-translate-y-2 shadow-lg hover:shadow-xl border border-white/10",
      },
      size: {
        default: "h-12 px-6 py-3 rounded-xl text-sm",
        sm: "h-10 px-4 py-2 rounded-lg text-sm",
        lg: "h-14 px-8 py-4 rounded-2xl text-lg",
        icon: "h-12 w-12 rounded-xl",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
