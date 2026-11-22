import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "outline" | "ghost" | "link";
};

const variants = {
  outline: "rounded-lg border px-2 py-1 disabled:opacity-50",
  ghost: "rounded-lg p-2 hover:bg-sidebar-accent",
  link: "mt-2 text-sm font-medium text-primary underline",
};

/** Plain button with the app's look. Pass className to add layout classes. */
export function Button({ variant = "outline", className = "", type = "button", ...rest }: Props) {
  return <button type={type} className={variants[variant] + " " + className} {...rest} />;
}
