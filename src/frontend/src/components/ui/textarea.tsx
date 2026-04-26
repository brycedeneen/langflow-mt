import * as React from "react";
import { cn } from "../../utils/utils";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  password?: boolean;
  editNode?: boolean;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, password, editNode, ...props }, ref) => {
    return (
      <div className="h-full w-full">
        <textarea
          data-testid="textarea"
          className={cn(
            "nopan nodelete nodrag noflow form-input block w-full rounded-md border border-border bg-background px-3 text-left text-sm placeholder:text-muted-foreground hover:border-muted-foreground focus:border-foreground focus:placeholder-transparent focus:ring-0 focus:ring-foreground disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground disabled:opacity-100 placeholder:disabled:text-muted-foreground nowheel",
            className,
            password ? "password" : "",
          )}
          ref={ref}
          {...props}
          value={props.value as string}
          onChange={props.onChange}
        />
      </div>
    );
  },
);

Textarea.displayName = "Textarea";

export { Textarea };
