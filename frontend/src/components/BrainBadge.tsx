import { cn } from "@/lib/utils";

type ProviderKey = "openai" | "anthropic" | "gemini" | string;

type BadgeVisual = {
  label: string;
  short: string;
  classes: string;
  title: string;
};

const BRAND: Record<string, BadgeVisual> = {
  openai: {
    label: "ChatGPT",
    short: "GPT",
    classes: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    title: "OpenAI — ChatGPT",
  },
  anthropic: {
    label: "Claude",
    short: "C",
    classes: "bg-orange-50 text-orange-700 ring-orange-200",
    title: "Anthropic — Claude",
  },
  gemini: {
    label: "Gemini",
    short: "G",
    classes: "bg-sky-50 text-sky-700 ring-sky-200",
    title: "Google — Gemini",
  },
};

const FALLBACK: BadgeVisual = {
  label: "LLM",
  short: "LLM",
  classes: "bg-slate-50 text-slate-700 ring-slate-200",
  title: "LLM",
};

export default function BrainBadge({
  provider,
  model,
  size = "sm",
  testId,
}: {
  provider: ProviderKey;
  model?: string;
  size?: "sm" | "xs";
  testId?: string;
}) {
  const visual = BRAND[provider] ?? FALLBACK;
  const title = model ? `${visual.title} · ${model}` : visual.title;
  return (
    <span
      title={title}
      aria-label={title}
      data-testid={testId}
      data-provider={provider}
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 font-mono font-semibold ring-1 ring-inset",
        visual.classes,
        size === "xs" ? "text-[9px]" : "text-[10px]",
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "inline-flex items-center justify-center rounded-full bg-white/70",
          size === "xs" ? "size-3 text-[8px]" : "size-3.5 text-[9px]",
        )}
      >
        {visual.short}
      </span>
      <span>{visual.label}</span>
    </span>
  );
}
